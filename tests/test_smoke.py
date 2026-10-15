"""End-to-end smoke tests for GH Diseños using FastAPI TestClient."""
import asyncio
import sys
import os

PROJECT_DIR = os.environ.get("GH_CORPS_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_DIR)

from httpx import AsyncClient, ASGITransport
from main import app

BASE = "http://test"

PASS = []
FAIL = []


def check(name, condition, extra=""):
    if condition:
        PASS.append(name)
        print(f"  OK  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name}  {extra}")


async def run():
    from app.core.database import init_db, async_session as setup_session
    from app.services.seed import seed_all
    from sqlalchemy import select, func, delete
    from app.core.database import async_session as test_session
    from app.core.config import settings
    from app.models.message import Message
    from app.models.message_attachment import MessageAttachment
    from app.models.user import User
    from app.models.product import Product
    from app.models.order import Order
    from app.models.cart_item import CartItem
    from app.models.review import Review
    from app.models.commission import Commission, CommissionMessage
    from app.models.notification import Notification

    await init_db()
    async with setup_session() as sdb:
        await seed_all(sdb)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE, follow_redirects=False) as c:
        print("== Public pages ==")
        r = await c.get("/")
        check("GET /", r.status_code == 200, str(r.status_code))

        r = await c.get("/shop")
        check("GET /shop", r.status_code == 200)

        r = await c.get("/product/1")
        check("GET /product/1", r.status_code in (200, 404), str(r.status_code))

        r = await c.get("/about")
        check("GET /about", r.status_code == 200)

        r = await c.get("/contact")
        check("GET /contact", r.status_code == 200)

        r = await c.get("/auth/login")
        check("GET /auth/login", r.status_code == 200)

        r = await c.get("/auth/register")
        check("GET /auth/register", r.status_code == 200)

        r = await c.get("/shop?category=solidworks")
        check("GET /shop?category=solidworks", r.status_code == 200)

        r = await c.get("/shop?search=motor")
        check("GET /shop?search=motor", r.status_code == 200)

        r = await c.get("/language/en")
        check("GET /language/en", r.status_code == 303, str(r.status_code))

        r = await c.get("/robots.txt")
        check("GET /robots.txt", r.status_code == 200 and "sitemap.xml" in r.text, str(r.status_code))

        r = await c.get("/sitemap.xml")
        check("GET /sitemap.xml", r.status_code == 200 and "<urlset" in r.text, str(r.status_code))

        r = await c.get("/esta-ruta-no-existe")
        check("GET unknown route -> custom 404", r.status_code == 404 and "not_found" in r.text or "Página no encontrada" in r.text or "Page not found" in r.text, str(r.status_code))

        r = await c.get("/")
        check("cookie banner rendered", "cookie-banner" in r.text, "")
        check("skip-to-content link present", "skip-link" in r.text, "")
        check("nav marks home active", "aria-current=" in r.text, "")

        r = await c.get("/shop")
        check("nav marks shop active", 'href="/shop"' in r.text and 'aria-current="page"' in r.text, "")

        print("== Anonymous buy/contact ==")
        PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        r = await c.post("/contact", data={
            "name": "Test User",
            "email": "test@example.com",
            "subject": "Hola",
            "message": "Quiero un plano personalizado",
        })
        check("POST /contact guest -> 303 sent", r.status_code == 303 and r.headers.get("location", "").endswith("?sent=1"), str(r.status_code) + " " + str(r.headers.get("location")))
        async with test_session() as db:
            guest_msg = (await db.execute(select(Message).where(Message.subject == "Hola", Message.user_id.is_(None)).order_by(Message.id.desc()).limit(1))).scalar_one_or_none()
        check("guest message stored with user_id None", guest_msg is not None, str(guest_msg))

        r = await c.post("/contact", data={
            "name": "Test User",
            "email": "",
            "subject": "Hola sin correo",
            "message": "Mensaje sin correo",
        })
        check("POST /contact guest missing email -> error", r.status_code == 303 and "error=1" in (r.headers.get("location") or ""), str(r.status_code) + " " + str(r.headers.get("location")))

        r = await c.post("/contact", data={
            "name": "Test User",
            "email": "test@example.com",
            "subject": "Hola con imagen",
            "message": "Mensaje con imagen",
        }, files={"files": ("foto.png", PNG, "image/png")})
        check("POST /contact guest with image -> 303 sent", r.status_code == 303 and r.headers.get("location", "").endswith("?sent=1"), str(r.status_code) + " " + str(r.headers.get("location")))
        async with test_session() as db:
            img_msg = (await db.execute(select(Message).where(Message.subject == "Hola con imagen").order_by(Message.id.desc()).limit(1))).scalar_one_or_none()
            att = None
            if img_msg is not None:
                att = (await db.execute(select(MessageAttachment).where(MessageAttachment.message_id == img_msg.id).limit(1))).scalar_one_or_none()
        check("guest image attachment stored", att is not None and str(att.path).lower().endswith(".png") and os.path.isfile(att.path), str(att))

        r = await c.post("/shop/buy/1")
        check("POST /shop/buy anonymous -> redirected to login", r.status_code == 303 and "auth/login" in (r.headers.get("location") or ""), str(r.status_code) + " " + str(r.headers.get("location")))

        r = await c.post("/cart/checkout")
        check("POST /cart/checkout anonymous -> redirected to login", r.status_code == 303 and "auth/login" in (r.headers.get("location") or ""), str(r.status_code) + " " + str(r.headers.get("location")))

        r = await c.get("/cart")
        check("GET /cart anonymous -> redirected to login", r.status_code == 303 and "auth/login" in (r.headers.get("location") or ""), str(r.status_code) + " " + str(r.headers.get("location")))

        r = await c.post("/review", data={"rating": "5", "comment": "spam"})
        check("POST /review anonymous -> redirected to login", r.status_code == 303 and "auth/login" in (r.headers.get("location") or ""), str(r.status_code) + " " + str(r.headers.get("location")))

        r = await c.get("/")
        check("cart icon hidden for anonymous", "cart3" not in r.text, "")

        print("== Register + login ==")
        unique_email = f"cliente{int(asyncio.get_event_loop().time())}@test.com"
        r = await c.post("/auth/register", data={
            "full_name": "Cliente Prueba",
            "email": unique_email,
            "password": "secret123",
            "confirm_password": "secret123",
            "gender": "mujer",
            "account_type": "persona",
        })
        check("POST /auth/register", r.status_code == 303, str(r.status_code))
        token = c.cookies.get("access_token")
        check("register sets token cookie", token is not None)

        # Duplicate check: register a fixed second user, then attempt duplicating it
        r = await c.post("/auth/register", data={
            "full_name": "Cliente Duplicado",
            "email": unique_email.upper(),
            "password": "secret123",
            "confirm_password": "secret123",
            "gender": "hombre",
            "account_type": "empresa",
        })
        check("register duplicate email blocked", r.status_code == 400, str(r.status_code))

        r = await c.post("/auth/register", data={
            "full_name": "Cliente Fijo",
            "email": "fijo@test.com",
            "password": "secret123",
            "confirm_password": "secret123",
            "gender": "hombre",
            "account_type": "persona",
        })
        check("register fixed user", r.status_code in (303, 400), str(r.status_code))

        r = await c.post("/auth/register", data={
            "full_name": "Bad",
            "email": "bad-email",
            "password": "123456",
            "confirm_password": "123456",
            "gender": "otro",
            "account_type": "persona",
        })
        check("register invalid email blocked", r.status_code == 400, str(r.status_code))

        r = await c.post("/auth/login", data={
            "email": unique_email,
            "password": "wrongpass",
        })
        check("login wrong password -> 400", r.status_code == 400, str(r.status_code))

        r = await c.post("/auth/login", data={
            "email": unique_email,
            "password": "secret123",
        })
        check("login ok -> 303", r.status_code == 303, str(r.status_code))

        print("== Client area ==")
        r = await c.get("/account")
        check("GET /account", r.status_code == 200, str(r.status_code))

        r = await c.get("/account/orders")
        check("GET /account/orders", r.status_code == 200)

        r = await c.get("/account/messages")
        check("GET /account/messages", r.status_code == 200)

        r = await c.post("/account/messages", data={
            "subject": "Pedido personalizado",
            "content": "Necesito un plano de una brida",
        }, files={"files": ("brida.png", PNG, "image/png")})
        check("POST /account/messages", r.status_code == 303, str(r.status_code))

        async with test_session() as db:
            client_msg_id = (await db.execute(select(Message.id).where(Message.subject == "Pedido personalizado"))).scalar_one_or_none()
            client_att_count = (await db.execute(select(func.count(MessageAttachment.id)).where(MessageAttachment.message_id == client_msg_id))).scalar_one()
        check("client message stored 1 image attachment", client_att_count == 1, str(client_att_count))

        r = await c.get("/account/messages?sent=1")
        check("dismissible success alert", r.status_code == 200 and "btn-close" in r.text, str(r.status_code))

        print("== Client commissions ==")
        r = await c.get("/account/commissions")
        check("GET /account/commissions", r.status_code == 200)

        r = await c.get("/account/commissions/new")
        check("GET /account/commissions/new", r.status_code == 200)

        commission_title = "Encargo de prueba UNIQ"
        r = await c.post("/account/commissions", data={
            "contact_name": "Cliente Prueba",
            "contact_email": unique_email,
            "title": commission_title,
            "description": "Necesito un plano estructural a medida para mi proyecto.",
        })
        check("POST /account/commissions", r.status_code == 303, str(r.status_code))
        async with test_session() as db:
            test_cid = (await db.execute(select(func.max(Commission.id)))).scalar()
        check("commission created", test_cid is not None)

        r = await c.get(f"/account/commissions/{test_cid}")
        check("GET client commission detail", r.status_code == 200 and commission_title in r.text, str(r.status_code))

        r = await c.post("/shop/buy/1")
        check("POST /shop/buy/1 (client, no product)", r.status_code == 404, str(r.status_code))

        print("== Admin access denied for client ==")
        r = await c.get("/admin")
        check("GET /admin as client -> 403", r.status_code == 403, str(r.status_code))

        print("== Logout ==")
        r = await c.get("/auth/logout")
        check("GET /auth/logout -> 303", r.status_code == 303, str(r.status_code))

        r = await c.get("/account")
        check("GET /account (no auth) -> 303 to login", r.status_code == 303, str(r.status_code))

        print("== Admin login ==")
        r = await c.post("/auth/login", data={
            "email": settings.COMPANY_EMAIL,
            "password": "admin1234",
        })
        check("admin login -> 303", r.status_code == 303, str(r.status_code))

        # Create a product so we can test buy/order flows
        r = await c.post("/admin/products/create", data={
            "name": "Plano de prueba",
            "description": "Producto para pruebas",
            "price": "25.00",
            "category": "autocad",
            "software": "AutoCAD 2023",
        })
        check("create product for buy test", r.status_code == 303, str(r.status_code))
        async with test_session() as db:
            test_pid = (await db.execute(select(func.max(Product.id)))).scalar()
        check("product id available", test_pid is not None)

        print("== Client buy flow ==")
        r = await c.get("/auth/logout")
        check("logout before client buy", r.status_code == 303)
        r = await c.post("/auth/login", data={
            "email": unique_email,
            "password": "secret123",
        })
        check("client re-login -> 303", r.status_code == 303, str(r.status_code))
        r = await c.post(f"/shop/buy/{test_pid}")
        check("POST /shop/buy/{pid} (client)", r.status_code == 303, str(r.status_code))
        async with test_session() as db:
            test_oid = (await db.execute(select(func.max(Order.id)))).scalar()
        check("order created", test_oid is not None)
        r = await c.get("/account/orders")
        check("GET /account/orders has order", r.status_code == 200)
        r = await c.get("/auth/logout")
        check("logout before admin", r.status_code == 303)
        r = await c.post("/auth/login", data={
            "email": settings.COMPANY_EMAIL,
            "password": "admin1234",
        })
        check("admin re-login -> 303", r.status_code == 303, str(r.status_code))

        r = await c.get("/admin")
        check("GET /admin", r.status_code == 200, str(r.status_code))
        check("dashboard shows monthly sales", "monthly_sales" in r.text or "Ventas mensuales" in r.text or "Monthly sales" in r.text, "")
        check("dashboard shows top products", "Top selling" in r.text or "más vendidos" in r.text or "plus vendus" in r.text, "")
        check("dashboard shows recent commission", commission_title in r.text, "")

        print("== Admin commissions ==")
        r = await c.get("/admin/commissions")
        check("GET /admin/commissions", r.status_code == 200 and commission_title in r.text, str(r.status_code))

        r = await c.get(f"/admin/commissions?q={commission_title.replace(' ', '+')}")
        check("search by title finds commission", r.status_code == 200 and commission_title in r.text, str(r.status_code))

        r = await c.get(f"/admin/commissions?q={unique_email.replace('@', '%40')}")
        check("search by client email finds commission", r.status_code == 200 and commission_title in r.text, str(r.status_code))

        r = await c.get("/admin/commissions?q=ninguna-cosa")
        check("search no match shows empty", r.status_code == 200 and commission_title not in r.text, str(r.status_code))

        r = await c.get("/admin/commissions?since=30")
        check("filter since=30 keeps new commission", r.status_code == 200 and commission_title in r.text, str(r.status_code))

        async with test_session() as db:
            unread_before = (
                await db.execute(
                    select(func.count(CommissionMessage.id)).where(
                        CommissionMessage.commission_id == test_cid,
                        CommissionMessage.is_read == False,
                    )
                )
            ).scalar()
        check("commission has 1 unread message", unread_before == 1, str(unread_before))

        r = await c.get(f"/admin/commissions/{test_cid}")
        check(
            "GET admin commission detail + client panel",
            r.status_code == 200
            and commission_title in r.text
            and ("Client data" in r.text or "Datos del cliente" in r.text or "Données du client" in r.text),
            str(r.status_code),
        )

        async with test_session() as db:
            unread_after = (
                await db.execute(
                    select(func.count(CommissionMessage.id)).where(
                        CommissionMessage.commission_id == test_cid,
                        CommissionMessage.is_read == False,
                    )
                )
            ).scalar()
        check("viewing detail marks messages as read", unread_after == 0, str(unread_after))

        r = await c.post(f"/admin/commissions/{test_cid}/messages", data={"content": "Prototipo inicial listo"})
        check("admin reply -> 303", r.status_code == 303, str(r.status_code))
        async with test_session() as db:
            unread_after_reply = (
                await db.execute(
                    select(func.count(CommissionMessage.id)).where(
                        CommissionMessage.commission_id == test_cid,
                        CommissionMessage.is_read == False,
                    )
                )
            ).scalar()
        check("admin reply keeps 0 unread", unread_after_reply == 0, str(unread_after_reply))

        r = await c.get("/admin/orders")
        check("GET /admin/orders", r.status_code == 200)

        r = await c.get("/admin/customers")
        check("GET /admin/customers", r.status_code == 200)

        r = await c.get("/admin/messages")
        check("GET /admin/messages", r.status_code == 200)

        r = await c.get("/admin/products")
        check("GET /admin/products", r.status_code == 200)

        r = await c.get("/admin/products/new")
        check("GET /admin/products/new", r.status_code == 200)

        r = await c.post(f"/admin/orders/{test_oid}/status", data={"status_value": "enviado"})
        check("POST order status update -> 303", r.status_code == 303, str(r.status_code))

        print("== Admin product CRUD (uses test_pid) ==")
        r = await c.post(f"/admin/products/{test_pid}/update", data={
            "name": "Plano test CRUD editado",
            "description": "Editado",
            "price": "15.00",
            "category": "otros",
            "software": "Photoshop CC",
            "is_available": "on",
        })
        check("POST update product -> 303", r.status_code == 303, str(r.status_code))

        r = await c.post(f"/admin/products/{test_pid}/delete")
        check("POST delete product -> 303", r.status_code == 303, str(r.status_code))

        print("== Admin messages ==")
        async with test_session() as db:
            client_msg_id = (
                await db.execute(
                    select(Message.id).where(Message.subject == "Pedido personalizado")
                )
            ).scalar_one_or_none()
        check("client message exists for admin tests", client_msg_id is not None)

        r = await c.get("/admin/messages?status_filter=unread")
        check("filter unread shows client message", r.status_code == 200 and "Pedido personalizado" in r.text, str(r.status_code))

        r = await c.post(f"/admin/messages/{client_msg_id}/read")
        check("POST mark message read -> 303", r.status_code == 303, str(r.status_code))

        r = await c.get("/admin/messages?q=pedido")
        check("search by subject finds message", r.status_code == 200 and "Pedido personalizado" in r.text, str(r.status_code))

        r = await c.get("/admin/messages?since=30")
        check("since=30 keeps message", r.status_code == 200 and "Pedido personalizado" in r.text, str(r.status_code))

        r = await c.post(f"/admin/messages/{client_msg_id}/reply", data={
            "reply_content": "Hola, te respondemos",
            "agent": "Henri",
        }, files={"files": ("diseno.png", PNG, "image/png")})
        check("POST reply message -> 303", r.status_code == 303, str(r.status_code))

        async with test_session() as db:
            reply_msg = (await db.execute(select(Message).order_by(Message.id.desc()).limit(1))).scalar_one()
            att_count = (await db.execute(select(func.count(MessageAttachment.id)).where(MessageAttachment.message_id == reply_msg.id))).scalar_one()
        check("reply linked to original", reply_msg.reply_to_id == client_msg_id, str(reply_msg.reply_to_id))
        check("reply attributed to support agent", reply_msg.sender_name == "Henri", reply_msg.sender_name)
        check("reply stored 1 image attachment", att_count == 1, str(att_count))

        r = await c.get(f"/admin/messages/{client_msg_id}")
        check(
            "admin detail shows thread",
            r.status_code == 200
            and "Hola, te respondemos" in r.text
            and ("Hilo" in r.text or "Thread" in r.text or "thread" in r.text or "Fil" in r.text),
            str(r.status_code),
        )

        r = await c.get("/admin/messages?status_filter=read")
        check("filter read shows replied message", r.status_code == 200 and "Pedido personalizado" in r.text, str(r.status_code))

        print("== Client sees admin reply ==")
        r = await c.get("/auth/logout")
        check("logout admin for client check", r.status_code == 303)
        r = await c.post("/auth/login", data={
            "email": unique_email,
            "password": "secret123",
        })
        check("client login -> 303", r.status_code == 303)
        r = await c.get("/account/messages")
        check("client sees admin reply in thread", r.status_code == 200 and "Hola, te respondemos" in r.text, str(r.status_code))

        print("== Client notifications ==")
        r = await c.get("/notifications")
        check("GET /notifications -> 200", r.status_code == 200, str(r.status_code))
        async with test_session() as db:
            client_uid = (await db.execute(select(User.id).where(User.email == unique_email))).scalar_one_or_none()
            nid = (
                await db.execute(
                    select(Notification.id).where(Notification.user_id == client_uid).limit(1)
                )
            ).scalar_one_or_none()
        check("client has at least one notification", nid is not None, str(nid))

        before = (await c.get("/notifications/unread-count")).json().get("count", 0)
        r = await c.post(f"/notifications/{nid}/read")
        check("POST single notification read -> ok", r.status_code == 200 and r.json().get("ok") is True, str(r.status_code))
        after = (await c.get("/notifications/unread-count")).json().get("count", -1)
        check("single read decreases unread count", after == before - 1, f"{before} -> {after}")

        r = await c.get("/auth/logout")
        check("logout client", r.status_code == 303)
        r = await c.post("/auth/login", data={
            "email": settings.COMPANY_EMAIL,
            "password": "admin1234",
        })
        check("admin re-login -> 303", r.status_code == 303)

        r = await c.post(f"/admin/messages/{client_msg_id}/delete")
        check("POST delete message -> 303", r.status_code == 303, str(r.status_code))

        print("== Admin review moderation ==")
        r = await c.get("/admin/reviews")
        check("GET /admin/reviews -> 200", r.status_code == 200, str(r.status_code))
        async with test_session() as db:
            demo_review_id = (await db.execute(select(Review.id).limit(1))).scalar_one_or_none()
        check("at least one review exists", demo_review_id is not None, str(demo_review_id))
        r = await c.post(f"/admin/reviews/{demo_review_id}/delete")
        check("POST admin review delete -> 303", r.status_code == 303, str(r.status_code))
        async with test_session() as db:
            review_gone = (await db.execute(select(Review.id).where(Review.id == demo_review_id))).scalar_one_or_none() is None
        check("review removed from DB", review_gone, "")

        print("== Cart flow ==")
        # logout admin, login client
        r = await c.get("/auth/logout")
        check("logout before cart flow", r.status_code == 303)
        r = await c.post("/auth/login", data={
            "email": unique_email,
            "password": "secret123",
        })
        check("client login for cart flow -> 303", r.status_code == 303, str(r.status_code))
        r = await c.get("/auth/logout")
        check("logout client, login admin to create cart product", r.status_code == 303)
        r = await c.post("/auth/login", data={
            "email": settings.COMPANY_EMAIL,
            "password": "admin1234",
        })
        check("admin relogin for cart product", r.status_code == 303, str(r.status_code))
        r = await c.post("/admin/products/create", data={
            "name": "Plano carrito",
            "description": "Producto para el carrito",
            "price": "30.00",
            "category": "solidworks",
            "software": "SolidWorks",
        })
        check("create product for cart test", r.status_code == 303, str(r.status_code))
        async with test_session() as db:
            cart_pid = (await db.execute(select(func.max(Product.id)))).scalar()
        check("cart product id available", cart_pid is not None)
        r = await c.get("/auth/logout")
        check("logout admin before cart", r.status_code == 303)
        r = await c.post("/auth/login", data={
            "email": unique_email,
            "password": "secret123",
        })
        check("client relogin for cart", r.status_code == 303, str(r.status_code))
        r = await c.post(f"/shop/cart/add/{cart_pid}")
        check("POST /shop/cart/add (client)", r.status_code == 303, str(r.status_code))
        r = await c.post(f"/shop/cart/add/{cart_pid}")
        check("POST add again -> 303", r.status_code == 303, str(r.status_code))
        r = await c.get("/cart")
        check("GET /cart", r.status_code == 200, str(r.status_code))
        check("GET /cart renders item", "qty_" in r.text, "")

        async with test_session() as db:
            user_id = (await db.execute(select(User.id).where(User.email == unique_email))).scalar_one()
            cart_rows = (await db.execute(
                select(func.count()).select_from(CartItem).where(CartItem.user_id == user_id)
            )).scalar()
        check("cart persisted to DB after add", cart_rows and cart_rows >= 1, str(cart_rows))

        r = await c.post("/cart/checkout")
        check("POST /cart/checkout (client) -> 303", r.status_code == 303, str(r.status_code))
        cart_cookie = c.cookies.get("cart")
        check("cart cookie cleared after checkout", cart_cookie in (None, ""), str(cart_cookie))
        async with test_session() as db:
            cart_rows_after = (await db.execute(
                select(func.count()).select_from(CartItem).where(CartItem.user_id == user_id)
            )).scalar()
        check("persisted cart cleared after checkout", (cart_rows_after or 0) == 0, str(cart_rows_after))

        print("== Notifications ==")
        # The client received an in-app notification when the admin updated the order status.
        r = await c.get("/notifications/unread-count")
        check("GET unread-count JSON", r.status_code == 200, str(r.status_code))
        check("client has unread notifications", r.json().get("count", 0) >= 1, "")

        r = await c.get("/notifications")
        check("GET /notifications -> 200", r.status_code == 200, str(r.status_code))
        check("notifications page renders list", "read-all" in r.text or "notif" in r.text, "")

        r = await c.post("/notifications/read-all")
        check("POST /notifications/read-all -> 303", r.status_code == 303, str(r.status_code))
        r = await c.get("/notifications/unread-count")
        check("unread-count is zero after read-all", r.json().get("count", -1) == 0, "")

        print("== Global reviews ==")
        r = await c.post("/review", data={"rating": "5", "comment": "Muy bueno, lo recomiendo"})
        check("POST /review (client) -> 303", r.status_code == 303, str(r.status_code))
        r = await c.get("/")
        check("home renders review widget", "review-widget" in r.text, "")
        check("review shows reviewer name", "Cliente Prueba" in r.text, "")
        check("review shows comment", "Muy bueno" in r.text, "")

        print("== My review management ==")
        r = await c.get("/account/review")
        check("GET /account/review -> 200", r.status_code == 200, str(r.status_code))
        check("my review page shows my comment", "Muy bueno" in r.text, "")
        r = await c.post("/account/review/delete")
        check("POST /account/review/delete -> 303", r.status_code == 303, str(r.status_code))
        r = await c.get("/account/review")
        check("my review page shows empty state", "review_none" in r.text or "no has dejado" in r.text or "not left a review" in r.text or "pas encore laissé" in r.text, "")

        print("== Change password ==")
        r = await c.get("/account/password")
        check("GET /account/password", r.status_code == 200, str(r.status_code))
        r = await c.post("/account/password", data={
            "current_password": "wrongpass",
            "new_password": "nueva123",
            "confirm_password": "nueva123",
        })
        check("change password wrong current -> 400", r.status_code == 400, str(r.status_code))
        r = await c.post("/account/password", data={
            "current_password": "secret123",
            "new_password": "nueva123",
            "confirm_password": "otrapass",
        })
        check("change password mismatch -> 400", r.status_code == 400, str(r.status_code))
        r = await c.post("/account/password", data={
            "current_password": "secret123",
            "new_password": "nueva123",
            "confirm_password": "nueva123",
        })
        check("change password ok -> 303", r.status_code == 303, str(r.status_code))
        r = await c.get("/auth/logout")
        check("logout after password change", r.status_code == 303)
        r = await c.post("/auth/login", data={"email": unique_email, "password": "nueva123"})
        check("login with new password -> 303", r.status_code == 303, str(r.status_code))

        print("== Gallery flow ==")
        r = await c.get("/auth/logout")
        check("logout client for gallery", r.status_code == 303)
        r = await c.post("/auth/login", data={
            "email": settings.COMPANY_EMAIL,
            "password": "admin1234",
        })
        check("admin login for gallery", r.status_code == 303, str(r.status_code))
        gallery_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 256
        r = await c.post(
            f"/admin/products/{cart_pid}/update",
            data={
                "name": "Plano carrito",
                "description": "Producto para el carrito",
                "price": "30.00",
                "category": "solidworks",
                "software": "SolidWorks",
                "is_available": "on",
            },
            files={"gallery_images": ("galeria1.png", gallery_bytes, "image/png")},
        )
        check("POST update product with gallery -> 303", r.status_code == 303, str(r.status_code))
        r = await c.get(f"/product/{cart_pid}")
        check("GET product detail -> 200", r.status_code == 200, str(r.status_code))
        check("product detail renders gallery main", "gallery-main" in r.text, "")
        check("product detail has lightbox", "lightbox" in r.text, "")

        r = await c.get("/shop")
        check("GET /shop -> 200", r.status_code == 200, str(r.status_code))

        r = await c.get("/sitemap.xml")
        check("sitemap lists products", "product/" in r.text, "")

        print("== Static assets ==")
        r = await c.get("/static/css/style.css")
        check("GET /static/css/style.css", r.status_code == 200)

        r = await c.get("/static/js/main.js")
        check("GET /static/js/main.js", r.status_code == 200)

    print()
    print(f"PASSED: {len(PASS)} | FAILED: {len(FAIL)}")
    if FAIL:
        print("FAILED TESTS:", FAIL)
        sys.exit(1)


asyncio.run(run())