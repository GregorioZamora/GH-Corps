# GH Diseños - Plataforma de Venta de Planos Técnicos

Plataforma web completa para la compra y venta de planos técnicos (blueprints/drawings) realizados en **SolidWorks** y **AutoCAD**, más un apartado de **otros encargos** (diseño, retoque o renderizado con herramientas como Photoshop y similares).

---

## 📋 Tabla de contenidos

1. [Descripción general](#descripción-general)
2. [Características principales](#características-principales)
3. [Stack tecnológico](#stack-tecnológico)
4. [Estructura del proyecto](#estructura-del-proyecto)
5. [Arquitectura y decisiones de diseño](#arquitectura-y-decisiones-de-diseño)
6. [Base de datos y modelo de datos](#base-de-datos-y-modelo-de-datos)
7. [Sistema de autenticación](#sistema-de-autenticación)
8. [Sistema de roles y permisos](#sistema-de-roles-y-permisos)
9. [Internacionalización (i18n)](#internacionalización-i18n)
10. [Módulos y funcionalidades](#módulos-y-funcionalidades)
11. [Instalación y puesta en marcha](#instalación-y-puesta-en-marcha)
12. [Configuración de Google OAuth2](#configuración-de-google-oauth2)
13. [Credenciales por defecto](#credenciales-por-defecto)
14. [Seguridad](#seguridad)
15. [Buenas prácticas de ingeniería aplicadas](#buenas-prácticas-de-ingeniería-aplicadas)
16. [Pruebas](#pruebas)
17. [Posibles mejoras futuras](#posibles-mejoras-futuras)

---

## Descripción general

**GH Diseños** es una aplicación web que permite a usuarios comprar planos técnicos profesionales realizados con software CAD. La plataforma está diseñada para:

- **Clientes**: navegar el catálogo, comprar planos, gestionar sus pedidos y contactar con la empresa mediante un sistema de mensajería interna.
- **Administradores**: gestionar el catálogo de productos, visualizar pedidos, acceder a la información de los clientes, gestionar mensajes y contactar con los clientes directamente.

La aplicación es **completamente responsive** (funciona en móvil, tablet y escritorio) y **multilingüe** (español, inglés y francés).

---

## Características principales

### 🌐 Internacionalización (i18n)
- Tres idiomas disponibles: **Español (es)**, **Inglés (en)** y **Francés (fr)**.
- Selector de idioma en la barra de navegación accesible desde cualquier página.
- El idioma seleccionado se guarda en una cookie (`lang`) para persistencia entre sesiones.
- Sistema de traducción basado en archivos JSON por idioma (`app/locales/{es,en,fr}.json`).
- Las claves se resuelven en tiempo de renderizado mediante la función `t(request, key)`.

### 📱 Diseño responsive
- Construido con **Bootstrap 5.3** (sistema de rejilla fluida).
- Menú de navegación colapsable en dispositivos móviles.
- Tablas con scroll horizontal en pantallas pequeñas.
- Cards y componentes que se adaptan al ancho de pantalla (`col-md-6 col-lg-4`, etc.).
- Testado para móviles (≥360px), tablets y escritorio.

### 🔐 Autenticación
- **Registro e inicio de sesión local** con email y contraseña (hash con bcrypt).
- **Recuperación de contraseña** mediante enlace por email (token JWT con `purpose: reset` válido 30 min).
- **Inicio de sesión con Google OAuth2** (permite iniciar sesión con cuentas de Google ya existentes).
- Sesiones basadas en **JWT (JSON Web Tokens)** almacenados en cookies `httpOnly`.
- Prevención de duplicados: si el email ya existe, se vincula la cuenta de Google al usuario existente.

### 📧 Notificaciones por email (Gmail SMTP)
- Avisos por correo al **admin** (nuevo mensaje, nuevo pedido, nuevo encargo, respuesta de cliente) y al **cliente** (respuesta del admin, cambio de estado del pedido a enviado/completado, avance del encargo, restablecimiento de contraseña).
- Configurable vía variables de entorno: `MAIL_ENABLED`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_FROM_NAME` (plantilla directa para **Gmail**: `smtp.gmail.com:587` + STARTTLS).
- Si el email no está configurado, el servicio simplemente lo registra en el log (el flujo web no se bloquea).

### 👥 Sistema de roles (RBAC)
| Rol | Descripción |
|-----|-------------|
| `admin` | Acceso total: panel de administración, pedidos, clientes, mensajes, encargos, productos. **Se asigna manualmente.** |
| `client` | Acceso al catálogo, compras, pedidos, perfil y contacto con la empresa a través de mensajes y encargos. No accede a información sensible. |

El rol de administrador **solo se otorga de forma manual** (modificando la base de datos o mediante el seed). No existe registro público con rol admin.

### 🛒 Tienda
- Catálogo de planos con búsqueda por texto y filtrado por categoría (SolidWorks, AutoCAD, Otros encargos).
- Página de detalle de producto con **imagen** de previsualización del plano.
- Compra directa que genera un pedido vinculado al cliente.
- **Paginación** (10 ítems por página, configurable con `ITEMS_PER_PAGE`).

### 📦 Gestión de pedidos
- **Cliente**: ve sus pedidos con estado y fecha (listado paginado).
- **Admin**: ve todos los pedidos con filtros por estado y paginación; acceso a una **página de detalle** con la información completa del cliente (email, teléfono, dirección), del producto y las notas del pedido.
- **Descarga del plano**: el admin adjunta el archivo del plano (con **previsualización** en el formulario del producto) al producto; el cliente puede **descargarlo** solo cuando su pedido está en estado **Enviado** o **Completado**.

### 🎨 Encargos a medida (prototipos/iteraciones)
- El visitante/cliente puede **crear un encargo** desde el formulario de contacto o desde su panel («Mis encargos»).
- Cada encargo es un **hilo conversacional** con historial de prototipos: cliente y admin intercambian mensajes y **adjuntos** (archivos de prototipo).
- Estados: `en_proceso`, `revision`, `completado`.
- **Admin**: panel de encargos con filtro por estado, cambio de estado (notifica por email al cliente) y respuesta en el hilo con adjuntos.
- Notificaciones por email al admin y al cliente en cada paso.

### 💬 Mensajería / Contacto
- **Cliente o visitante**: envía mensajes vía formulario de contacto o desde su panel.
- **Admin**: panel de mensajes (paginado) con opciones de marcar como leído, responder y eliminar. Las respuestas quedan registradas en el historial del cliente.
- El contacto distingue entre **mensaje/consulta** y **encargo a medida** (campo `kind`).

### ⚖️ Páginas legales
- **Aviso legal**, **Política de privacidad** y **Política de cookies**, enlazadas en el pie de página y traducidas a los tres idiomas.

### 🔎 SEO
- Meta tags de **Open Graph** y descripción por página; páginas de producto generan `og:title`, `og:description` y `og:image` dinámicos.
- Imágenes de producto con `loading="lazy"` y `alt` descriptivo.

### 📊 Panel de administración
- Resumen estadístico (pedidos, clientes, ingresos, mensajes sin leer, encargos, productos).
- Gestión completa de productos (crear, editar, eliminar, activar/desactivar) con subida de **archivo del plano** e **imagen** y previsualización de ambos en el formulario.
- Listado de clientes con búsqueda por nombre/email/teléfono.
- Acceso a pedidos con filtros de estado, paginación y detalle ampliado.
- Gestión de encargos con hilos de conversación y adjuntos.

---

## Stack tecnológico

### Backend
| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| [Python](https://www.python.org/) | 3.10+ | Lenguaje principal |
| [FastAPI](https://fastapi.tiangolo.com/) | 0.104 | Framework web asíncrono de alto rendimiento |
| [Uvicorn](https://www.uvicorn.org/) | 0.24 | Servidor ASGI |
| [SQLAlchemy 2.0](https://www.sqlalchemy.org/) | 2.0 | ORM (Object-Relational Mapping) asíncrono |
| [aiosqlite](https://github.com/omnilib/aiosqlite) | 0.19 | Driver base de datos SQLite asíncrono |
| [Jinja2](https://jinja.palletsprojects.com/) | 3.1 | Motor de plantillas server-side |

### Autenticación y seguridad
| Tecnología | Propósito |
|------------|-----------|
| [python-jose](https://github.com/mpdavis/python-jose) | Generación/verificación de JWT |
| [passlib + bcrypt](https://passlib.readthedocs.io/) | Hash seguro de contraseñas |
| [httpx](https://www.python-httpx.org/) | Cliente HTTP asíncrono para llamadas a la API de Google |

### Frontend
| Tecnología | Propósito |
|------------|-----------|
| Bootstrap 5.3.2 | Framework CSS responsive (CDN) |
| Bootstrap Icons | Iconografía (CDN) |
| Vanilla JS | Interacción ligera del lado del cliente |

### Database
- **SQLite** (por defecto, mediante URL `sqlite+aiosqlite:///./gh_corps.db`). Cambiable a PostgreSQL/MySQL editando `DATABASE_URL` en el `.env`.

---

## Estructura del proyecto

```
GH Corps/
├── main.py                        # Punto de entrada de la aplicación (FastAPI app)
├── requirements.txt               # Dependencias de Python
├── .env.example                   # Ejemplo de variables de entorno
├── alembic.ini                    # Configuración de Alembic
├── alembic/                       # Migraciones de base de datos (Alembic)
│   ├── env.py                     # Conexión + target_metadata (Base.metadata)
│   └── versions/                  # Scripts de migración versionados
├── gh_corps.db                    # Base de datos SQLite (se genera automáticamente)
│
├── app/
│   ├── __init__.py
│   │
│   ├── core/                      # Núcleo de la aplicación
│   │   ├── __init__.py
│   │   ├── config.py              # Configuración centralizada (Settings)
│   │   ├── database.py            # Motor, sesión y conexión a BBDD
│   │   ├── security.py            # Passwords, JWT, dependencias de usuario/roles
│   │   ├── i18n.py                # Middleware de internacionalización
│   │   └── templating.py          # Instancias Jinja2Templates con globals compartidos
│   │
│   ├── models/                    # Modelos ORM (SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── user.py                # Modelo User
│   │   ├── product.py             # Modelo Product
│   │   ├── order.py               # Modelo Order
│   │   ├── message.py             # Modelo Message
│   │   └── commission.py          # Modelos Commission y CommissionMessage
│   │
│   ├── routes/                    # Rutas/controladores (API + vistas)
│   │   ├── __init__.py
│   │   ├── pages.py               # Páginas públicas (home, about, contact, legales, idioma)
│   │   ├── auth.py                # Autenticación (local + Google OAuth2 + reset contraseña)
│   │   ├── shop.py                # Tienda (catálogo, detalle, compra)
│   │   ├── client.py              # Área de cliente (cuenta, pedidos, mensajes, encargos)
│   │   └── admin.py               # Panel de administración (CRUD completo + encargos)
│   │
│   ├── services/                  # Lógica de negocio reutilizable
│   │   ├── __init__.py
│   │   ├── google_oauth.py        # Integración con Google OAuth2
│   │   ├── i18n_helper.py         # Helpers de traducción (t, tf)
│   │   ├── mailer.py              # Envío de emails (SMTP con fallback a log)
│   │   ├── pagination.py          # Helper de paginación
│   │   ├── uploads.py             # Guardado/borrado de archivos (planos, imágenes, adjuntos)
│   │   └── seed.py                # Creación del administrador por defecto
│   │
│   ├── templates/                 # Vistas (Jinja2, SSR)
│   │   ├── base.html              # Layout base (navbar + footer + i18n + meta SEO/OG)
│   │   ├── home.html              # Página de inicio
│   │   ├── about.html             # Página "Sobre nosotros"
│   │   ├── contact.html           # Página de contacto (mensaje o encargo)
│   │   ├── partials/pagination.html  # Paginador reutilizable
│   │   ├── legal/                 # Páginas legales
│   │   │   ├── aviso_legal.html
│   │   │   ├── privacidad.html
│   │   │   └── cookies.html
│   │   ├── auth/                  # Login, registro y recuperación de contraseña
│   │   │   ├── login.html
│   │   │   ├── register.html
│   │   │   ├── forgot_password.html
│   │   │   └── reset_password.html
│   │   ├── shop/                  # Tienda
│   │   │   ├── shop.html
│   │   │   └── product_detail.html
│   │   ├── client/                # Área de cliente
│   │   │   ├── dashboard.html
│   │   │   ├── orders.html
│   │   │   ├── messages.html
│   │   │   ├── commissions.html
│   │   │   ├── commission_form.html
│   │   │   └── commission_detail.html
│   │   └── admin/                 # Panel de administración
│   │       ├── dashboard.html
│   │       ├── orders.html
│   │       ├── order_detail.html
│   │       ├── customers.html
│   │       ├── messages.html
│   │       ├── products.html
│   │       ├── product_form.html
│   │       ├── commissions.html
│   │       └── commission_detail.html
│   │
│   ├── static/                    # Recursos estáticos
│   │   ├── css/style.css          # Estilos personalizados
│   │   └── js/main.js             # JavaScript ligero
│   │
│   └── locales/                   # Archivos de traducción (i18n)
│       ├── es.json                # Español
│       ├── en.json                # Inglés
│       └── fr.json                # Francés
│
└── uploads/                       # Uploads de usuarios (planos, imágenes, adjuntos)
```

---

## Arquitectura y decisiones de diseño

### Patrón de arquitectura
Se utiliza una arquitectura **en capas (layered architecture)** dentro de cada módulo:

```
┌─────────────────┐
│  Routes (Capa de presentación/peticiones HTTP)  │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Services (Capa de lógica de negocio)             │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Models (Capa de acceso a datos / ORM)            │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Database (SQLite)                               │
└─────────────────┘
```

El **controlador (route)** se limita a recoger la petición, delegar en servicios si es necesario, y renderizar la respuesta (TemplateResponse de Jinja2). La lógica de negocio que se repite (autenticación, OAuth, seed) vive en `app/services/`.

### FastAPI sobre Django/Flask — ¿por qué?
- **Rendimiento asíncrono**: todo el stack es `async/await` (rutas, ORM con aiosqlite, sesiones de BBDD).
- **Tipado moderno**: FastAPI integra *type hints* de Python 3.10+ en el propio framework.
- **Dependencias por inyección**: el sistema de `Depends()` de FastAPI se usa para inyección de sesiones BBDD, autenticación y control de roles (`require_role`). Es una práctica de ingeniería equivalente a los *DI containers* de frameworks empresariales.
- **SSR con Jinja2**: al ser una aplicación de catálogo/gestión, el server-side rendering simplifica el desarrollo, mejora el SEO y evita la complejidad de un SPA sin beneficiarse de él.

### Server-Side Rendering (SSR)
Todas las vistas se renderizan en el servidor con **Jinja2**, reutilizando el layout base (`base.html`) con herencia de plantillas:

- `{% extends "base.html" %}`
- `{% block content %}` / `{% block title %}` / `{% block extra_js %}`

El contexto incluye siempre `request`, `lang`, `_t` (función de traducción) y `current_user`.

### Gestión de configuración
Toda la configuración se centraliza en `app/core/config.py` mediante una clase `Settings` que lee las variables de entorno desde `.env` (cargado con `python-dotenv`). Esto permite cambiar de base de datos, claves secretas o credenciales de Google sin tocar código.

### Sesiones de base de datos
Se usa el patrón **dependency injection** de FastAPI: `get_db()` es una dependencia que abre una sesión async (`async_sessionmaker`), la inyecta en la ruta y la cierra automáticamente al finalizar:

```python
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

---

## Base de datos y modelo de datos

### Diagrama de entidades

```
┌────────────────────────────┐
│          User             │
│────────────────────────────│
│ id (PK)                    │
│ email (unique, index)      │
│ full_name                  │
│ hashed_password (nullable) │
│ role ('admin' | 'client')  │
│ is_active                  │
│ auth_provider ('local'|'google') │
│ gender / account_type      │
│ phone / address            │
│ google_id (nullable)       │
│ avatar_url (nullable)      │
│ created_at                 │
└────────────┬───────────────┘
             │ 1
             │
             │ N
┌────────────▼───────────────┐     ┌────────────────────────────┐
│          Order             │     │          Product           │
│────────────────────────────│     │────────────────────────────│
│ id (PK)                    │     │ id (PK)                    │
│ user_id (FK → User)        │     │ name                       │
│ product_id (FK → Product)  │     │ description                │
│ quantity                   │     │ category                   │
│ total_price                │     │ price                      │
│ status                     │     │ software                   │
│ notes (nullable)           │     │ file_path (nullable)       │
│ created_at                 │     │ image_path (nullable)      │
└────────────────────────────┘     │ is_available               │
                                   │ created_at                 │
┌────────────────────────────┐     └────────────────────────────┘
│          Message           │
│────────────────────────────│
│ id (PK)                    │
│ user_id (FK → User, null)  │
│ sender_name                │
│ sender_email               │
│ subject                    │
│ content                    │
│ is_read                    │
│ created_at                 │
└────────────────────────────┘

┌────────────────────────────┐
│        Commission          │        ┌────────────────────────────┐
│────────────────────────────│        │   CommissionMessage       │
│ id (PK)                    │ 1      │────────────────────────────│
│ user_id (FK → User, null)  ├───────►│ id (PK)                    │
│ title                      │    N   │ commission_id (FK)         │
│ description                │        │ sender_id (FK → User, null)│
│ client_name / client_email │        │ content                    │
│ status ('en_proceso'|'revision'|'completado') │ attachment_path │
│ created_at / updated_at    │        │ created_at                 │
└────────────────────────────┘        └────────────────────────────┘
```

### Detalle de tablas

#### `users`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer PK | Identificador |
| `email` | String(255) UNIQUE | Email de acceso |
| `full_name` | String(255) | Nombre completo |
| `hashed_password` | String(255) NULL | Hash bcrypt (null si es solo Google) |
| `role` | String(50) | `admin` o `client` |
| `is_active` | Boolean | Usuario activo |
| `auth_provider` | String(50) | `local` o `google` |
| `gender` | String(50) NULL | Género (`hombre`, `mujer`, `otro`) |
| `account_type` | String(50) NULL | Tipo de cuenta (`persona`, `empresa`) |
| `phone` | String(50) NULL | Teléfono de contacto |
| `address` | String(255) NULL | Dirección |
| `google_id` | String(255) NULL | ID de Google (para OAuth) |
| `avatar_url` | String(512) NULL | Avatar de Google |
| `created_at` | DateTime | Fecha de registro |

#### `products`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer PK | Identificador |
| `name` | String(255) | Nombre del plano |
| `description` | Text NULL | Descripción |
| `category` | String(100) | `solidworks`, `autocad`, `otros` |
| `price` | Float | Precio en € |
| `software` | String(100) NULL | Software de origen del plano |
| `file_path` | String(512) NULL | Ruta del fichero del plano |
| `image_path` | String(512) NULL | Ruta de imagen del producto |
| `is_available` | Boolean | Visible/comprable |
| `created_at` | DateTime | Fecha de alta |

#### `orders`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer PK | Identificador |
| `user_id` | FK → users.id | Cliente que compra |
| `product_id` | FK → products.id | Plano comprado |
| `quantity` | Integer | Cantidad |
| `total_price` | Float | Importe total |
| `status` | String(50) | `pendiente`, `enviado`, `completado`, `cancelado` |
| `notes` | Text NULL | Notas del pedido |
| `created_at` | DateTime | Fecha del pedido |

#### `messages`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer PK | Identificador |
| `user_id` | FK → users.id NULL | Usuario si está registrado |
| `sender_name` | String(255) | Nombre del remitente |
| `sender_email` | String(255) | Email del remitente |
| `subject` | String(255) | Asunto |
| `content` | Text | Cuerpo del mensaje |
| `is_read` | Boolean | Leído/no leído |
| `created_at` | DateTime | Fecha del mensaje |

#### `commissions`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer PK | Identificador |
| `user_id` | FK → users.id NULL | Cliente registrado (null si el encargo se creó como visitante) |
| `title` | String(255) | Título del trabajo a medida |
| `description` | Text NULL | Descripción del encargo |
| `client_name` | String(255) NULL | Nombre del cliente (para encargos sin cuenta) |
| `client_email` | String(255) NULL | Email del cliente (para encargos sin cuenta) |
| `status` | String(50) | `en_proceso`, `revision`, `completado` |
| `created_at` | DateTime | Fecha de creación |
| `updated_at` | DateTime | Última actualización |

#### `commission_messages`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer PK | Identificador |
| `commission_id` | FK → commissions.id | Encargo al que pertenece |
| `sender_id` | FK → users.id NULL | Usuario emisor (null si es visitante) |
| `content` | Text NULL | Cuerpo del mensaje |
| `attachment_path` | String(512) NULL | Ruta del prototipo adjunto |
| `created_at` | DateTime | Fecha del mensaje |

### Migraciones (Alembic)
El proyecto usa **Alembic** para el control versionado del esquema. La primera migración (`initial schema`) contiene el esquema completo.

```bash
# Aplicar todas las migraciones pendientes
alembic upgrade head

# Generar una nueva migración tras modificar un modelo
alembic revision --autogenerate -m "describe el cambio"
alembic upgrade head

# Ver el estado actual de la base de datos
alembic current
```

`alembic/env.py` lee la URL de la base de datos desde `DATABASE_URL`/`.env` y usa `Base.metadata` de la aplicación como `target_metadata`. Junto con Alembic, la app sigue creando tablas automáticamente en el primer arranque (`init_db()`), por lo que ambas vías conviven sin conflicto.

---

## Sistema de autenticación

### Flujo de registro/inicio local

```
Cliente → POST /auth/register
    ├── Validación: email válido, contraseñas coinciden, email no repetido
    ├── Hash bcrypt de la contraseña (get_password_hash)
    └── Creación del usuario con rol = 'client' (SIEMPRE)
        → Se genera JWT → Cookie httpOnly → Redirect /account

Cliente → POST /auth/login
    ├── Búsqueda por email (normalizado a minúsculas)
    ├── verify_password(plain, hash)
    └── JWT → Cookie httpOnly → Redirect /account
```

### Flujo de recuperación de contraseña

```
Cliente → GET /auth/forgot-password
    ├── Introduce su email

Cliente → POST /auth/forgot-password
    ├── Genera JWT {"sub": user_id, "purpose": "reset"} (validez 30 min,
    │       RESET_EXPIRE_MINUTES)
    ├── Envía enlace por email (notify_user)
    └── Redirect /auth/forgot-password?sent=1   (siempre, no filtra emails)

Cliente → GET /auth/reset-password?token=...
    ├── Verifica payload: purpose == 'reset' y token sin expirar
    └── Formulario de nueva contraseña

Cliente → POST /auth/reset-password
    ├── Nueva contraseña + confirmación → hash bcrypt
    ├── Notifica por email
    └── Redirect /auth/login?reset=1
```

### Flujo de Google OAuth2

```
Cliente → GET /auth/google
    ├── Redirige a accounts.google.com/o/oauth2/v2/auth
    │       (client_id, redirect_uri, scope=openid email profile, state)
Cliente → GET /auth/google/callback?code=...
    ├── POST https://oauth2.googleapis.com/token (exchange code → access_token)
    ├── GET https://www.googleapis.com/oauth2/v2/userinfo (email, name, picture, id)
    ├── ¿Existe usuario con ese google_id?  → loguear
    │   ¿Existe usuario con ese email?      → vincular google_id + loguear
    │   ¿No existe?                          → crear usuario (rol client) + loguear
    └── JWT → Cookie httpOnly → Redirect /account
```

### Sesiones JWT
- El token contiene `{"sub": <user_id>, "exp": <expiración>}`.
- Se firma con **HS256** usando `SECRET_KEY` del `.env`.
- Vida por defecto: **60 minutos** (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Cookie `httpOnly` (no accesible desde JS → protege contra XSS) y `max_age=604800` (7 días).

### Dependencias de autenticación (FastAPI DI)
| Dependencia | Comportamiento |
|-------------|----------------|
| `get_current_user` | Requiere token válido; si no, redirige a `/auth/login`. Se usa en rutas protegidas de cliente. |
| `get_optional_user` | Devuelve el usuario si hay token, si no `None`. Se usa en páginas públicas para personalizar la navbar. |
| `require_role("admin")` | Requiere token + rol `admin`; si el rol no coincide devuelve **403 Forbidden**. |

---

## Sistema de roles y permisos

### Asignación manual del rol `admin`
El rol de administrador **nunca** se asigna mediante registro público (el registro siempre crea `client`). Se concede de forma manual de dos maneras:

1. **Seed automático**: al arrancar la app por primera vez se crea el usuario `infoghdisenos@gmail.com` con rol `admin` (ver [Credenciales por defecto](#credenciales-por-defecto)).

2. **SQL manual** (promoción de un cliente existente):
   ```sql
   UPDATE users SET role = 'admin' WHERE email = 'cliente@example.com';
   ```
   O mediante consola interactiva:
   ```python
   # Desde un script Python con la sesión asíncrona
   ```

### Matriz de permisos
| Recurso / Acción | Visitante | Cliente | Admin |
|------------------|:---------:|:-------:|:-----:|
| Ver página de inicio | ✅ | ✅ | ✅ |
| Ver catálogo de planos | ✅ | ✅ | ✅ |
| Ver detalle de producto | ✅ | ✅ | ✅ |
| Comprar un plano | ❌ (requiere login) | ✅ | ✅ |
| Ver sus propios pedidos | ❌ | ✅ | ✅ |
| Ver pedidos de todos los clientes | ❌ | ❌ | ✅ |
| Cambiar estado de pedidos | ❌ | ❌ | ✅ |
| Enviar mensaje de contacto | ✅ | ✅ | ✅ |
| Ver información de clientes (email, registro) | ❌ | ❌ | ✅ |
| Gestionar productos (CRUD) | ❌ | ❌ | ✅ |
| Gestionar mensajes (leer/responder/eliminar) | ❌ | ❌ | ✅ |
| Ver panel de administración | ❌ | ❌ (403) | ✅ |

> **Privacidad**: el cliente **solo** ve sus propios pedidos y mensajes. La información de otros clientes (emails, fechas, pedidos ajenos) es exclusiva del rol `admin`.

---

## Internacionalización (i18n)

### Cómo funciona
1. Cada idioma tiene un **archivo JSON** en `app/locales/` con estructura de claves anidadas.
2. Un **middleware** (`I18nMiddleware`) lee la cookie `lang` en cada petición y carga las traducciones en `request.state`.
3. En las plantillas se accede mediante `_t('clave.nivel1.nivel2')`.
4. El endpoint `/language/{lang}` cambia el idioma y fija la cookie.

```python
# app/core/i18n.py — resolución de traducciones
t = lambda k: translations[k]  # resuelve "home.hero_title" → "Planos técnicos..."
```

```jinja2
<!-- En plantilla -->
<button>{{ _t('shop.buy') }}</button>
```

### Añadir un nuevo idioma
1. Copiar `es.json` a `locales/xx.json` y traducir todos los valores.
2. Añadir `"xx"` a `SUPPORTED_LANGUAGES` en `config.py`.
3. Añadir el enlace en el desplegable de idioma de `base.html`.

---

## Módulos y funcionalidades

### Rutas públicas (`pages.py`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Portada con hero y ventajas |
| GET | `/about` | Información de la empresa |
| GET | `/contact` | Formulario de contacto (mensaje o encargo a medida) |
| POST | `/contact` | Procesa el formulario (guarda en `messages` o crea `Commission`) |
| GET | `/legal/aviso-legal` | Aviso legal |
| GET | `/legal/privacidad` | Política de privacidad |
| GET | `/legal/cookies` | Política de cookies |
| GET | `/language/{lang}` | Cambia el idioma (cookie) |

### Tienda (`shop.py`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/shop` | Catálogo (filtros por categoría + búsqueda + paginación) |
| GET | `/product/{id}` | Detalle del plano |
| POST | `/shop/buy/{id}` | Compra directa → crea pedido |

### Autenticación (`auth.py`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/auth/login` | Página de login |
| POST | `/auth/login` | Procesa login local |
| GET | `/auth/register` | Página de registro |
| POST | `/auth/register` | Procesa registro local |
| GET | `/auth/google` | Inicia flujo Google OAuth2 |
| GET | `/auth/google/callback` | Callback tras éxito de Google |
| GET | `/auth/forgot-password` | Formulario "¿Olvidaste tu contraseña?" |
| POST | `/auth/forgot-password` | Envía enlace de restablecimiento por email |
| GET | `/auth/reset-password` | Formulario de nueva contraseña (token) |
| POST | `/auth/reset-password` | Guarda la nueva contraseña |
| GET | `/auth/logout` | Cierra sesión (borra cookie) |

### Cliente (`client.py`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/account` | Panel del cliente |
| GET | `/account/profile` | Formulario de edición de perfil |
| POST | `/account/profile` | Guarda cambios del perfil (nombre, email, género, tipo, teléfono, dirección) |
| GET | `/account/orders` | Mis pedidos (paginado) |
| GET | `/account/orders/{id}/download` | Descarga el archivo del plano (solo si el pedido está enviado/completado) |
| GET | `/account/messages` | Mis mensajes + formulario |
| POST | `/account/messages` | Envía mensaje |
| GET | `/account/commissions` | Mis encargos (paginado) |
| GET | `/account/commissions/new` | Formulario de nuevo encargo |
| POST | `/account/commissions` | Crea encargo + primer mensaje |
| GET | `/account/commissions/{id}` | Hilo del encargo |
| POST | `/account/commissions/{id}/messages` | Responde en el hilo (con adjunto opcional) |

### Administración (`admin.py`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin` | Dashboard con estadísticas |
| GET | `/admin/orders` | Todos los pedidos (filtro por estado + paginación) |
| GET | `/admin/orders/{id}` | Detalle ampliado del pedido (cliente, producto, notas) |
| POST | `/admin/orders/{id}/status` | Cambia estado del pedido |
| GET | `/admin/customers` | Listado de clientes (búsqueda + paginación) |
| GET | `/admin/messages` | Bandeja de mensajes (paginada) |
| POST | `/admin/messages/{id}/read` | Marcar leído |
| POST | `/admin/messages/{id}/delete` | Eliminar mensaje |
| POST | `/admin/messages/{id}/reply` | Responder (queda en historial del cliente) |
| GET | `/admin/products` | Listado de productos (búsqueda + paginación) |
| GET | `/admin/products/new` | Formulario nuevo producto |
| GET | `/admin/products/{id}/edit` | Formulario edición |
| POST | `/admin/products/create` | Crear producto (archivo + imagen con preview) |
| POST | `/admin/products/{id}/update` | Actualizar producto (archivo + imagen) |
| POST | `/admin/products/{id}/delete` | Eliminar producto |
| GET | `/admin/commissions` | Encargos (filtro por estado + paginación) |
| GET | `/admin/commissions/{id}` | Detalle/hilo del encargo |
| POST | `/admin/commissions/{id}/status` | Cambia estado del encargo |
| POST | `/admin/commissions/{id}/messages` | Responde en el hilo con adjunto |

---

## Instalación y puesta en marcha

### Requisitos previos
- Python **3.10 o superior**
- `pip`
- (Opcional) un entorno virtual

### 1. Crear entorno virtual (recomendado)

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
# Copiar el ejemplo
copy .env.example .env        # Windows
cp .env.example .env          # Linux/macOS
```

Editar `.env`:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `SECRET_KEY` | Clave de firma de JWT (cambiar en producción) | `super-secreto` |
| `DATABASE_URL` | Cadena de conexión | `sqlite+aiosqlite:///./gh_corps.db` |
| `GOOGLE_CLIENT_ID` | Cliente de Google OAuth (ver abajo) | `1234.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Secreto del cliente de Google | `GOCSPX-...` |
| `GOOGLE_REDIRECT_URI` | URI de callback autorizada | `http://localhost:8000/auth/google/callback` |
| `ADMIN_EMAIL` | Destinatario de las notificaciones al admin | `infoghdisenos@gmail.com` |
| `ITEMS_PER_PAGE` | Número de elementos por página (paginación) | `10` |
| `MAIL_ENABLED` | Activa/desactiva el envío de emails | `false` |
| `SMTP_HOST` | Servidor SMTP | `smtp.gmail.com` |
| `SMTP_PORT` | Puerto SMTP (587 para STARTTLS) | `587` |
| `SMTP_USER` | Usuario SMTP (email Gmail) | `tu.cuenta@gmail.com` |
| `SMTP_PASSWORD` | Contraseña / app password de Gmail | `abcd efgh ijkl mnop` |
| `MAIL_FROM` | Remitente | `tu.cuenta@gmail.com` |
| `MAIL_FROM_NAME` | Nombre visible del remitente | `GH Diseños` |

> ⚠️ Si dejas `GOOGLE_CLIENT_ID` vacío, el botón de Google no se mostrará en el login, pero el login/registro local sigue funcionando.
> 🔒 **Gmail**: genera una *contraseña de aplicación* (No: *App passwords*, 16 caracteres sin espacios) en tu cuenta de Google. Con `MAIL_ENABLED=false` el servicio solo registra los emails en el log de la aplicación.

### 4. Arrancar la aplicación

```bash
uvicorn main:app --reload --port 8000
```

O alternativamente:

```bash
python main.py
```

La aplicación estará disponible en **http://localhost:8000**

> Al primer arranque se crean las tablas de la base de datos y el usuario administrador automáticamente (`app/services/seed.py`). No se crean productos de ejemplo.

### 5. Comprobar

Abre `http://localhost:8000` y verás la portada de GH Diseños.

---

## Configuración de Google OAuth2

1. Ve a **[Google Cloud Console](https://console.cloud.google.com/)**.
2. Crea un proyecto (o usa uno existente).
3. Ve a **APIs & Services → OAuth consent screen**:
   - Tipo de usuario: **External** (o Internal si es para tu organización).
   - Añade el scope `openid`, `email`, `profile`.
4. Ve a **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Tipo: **Web application**.
   - **Authorized redirect URIs**: añade `http://localhost:8000/auth/google/callback`.
5. Copia el **Client ID** y el **Client Secret** al `.env`.
6. Reinicia la aplicación.

> En producción, la URI de callback debe apuntar a tu dominio real (ej. `https://tudominio.com/auth/google/callback`).

---

## Credenciales por defecto

### Administrador (creado automáticamente al primer arranque)
| Campo | Valor |
|-------|-------|
| Email | `infoghdisenos@gmail.com` |
| Contraseña | `admin1234` |
| Rol | `admin` |

> 🔐 **IMPORTANTE**: cambia esta contraseña antes de publicar la aplicación en producción. Para cambiar el rol de cualquier usuario, consulta la sección [Asignación manual del rol admin](#asignación-manual-del-rol-admin).

### Usuarios de ejemplo
Puedes crear cualquier usuario mediante el formulario de registro (siempre tendrá rol `client`).

---

## Seguridad

Medidas de seguridad implementadas:

1. **Hash de contraseñas** con **bcrypt** (salt automático, algoritmo resistente a fuerza bruta).
2. **Cookies `httpOnly`** para el token: no accesibles desde JavaScript → mitigación de **XSS**.
3. **JWT firmados** (HS256) con expiración: mitigación de **tampering** y sesiones robadas a largo plazo.
4. **Normalización de emails** (minúsculas) para evitar duplicados/collisiones.
5. **Control de acceso (RBAC)** con bloqueo de rutas admin mediante `require_role("admin")` → **403** si no se tiene el rol.
6. **Validación de formularios** en servidor (email con regex, contraseña mínima 6 caracteres, coincidencia de contraseñas).
7. **Escapado automático de Jinja2**: por defecto, todo `{{ variable }}` escapa HTML → mitigación de **XSS** en contenido generado por usuarios.
8. **No se exponen datos sensibles**: las rutas de cliente sólo devuelven datos del usuario autenticado (`current_user.id`).
9. **Archivo `.env` excluido** del repositorio con claves secretas.

### Notas para producción
- Usar clave `SECRET_KEY` larga y aleatoria.
- Migrar a una base de datos PostgreSQL/MySQL (cambiar `DATABASE_URL`).
- Servir la aplicación detrás de HTTPS (reverse proxy como Nginx + certificado TLS).
- Desactivar el modo debug de Uvicorn.

---

## Buenas prácticas de ingeniería aplicadas

- **Separación de responsabilidades** (Routes / Services / Models / Templates / Static).
- **Configuración externalizada** (12-factor): `.env` y clase `Settings`.
- **Inyección de dependencias** de FastAPI para BBDD y autenticación.
- **Código asíncrono** de principio a fin (FastAPI async + SQLAlchemy async + aiosqlite).
- **Reutilización de plantillas** mediante herencia de Jinja2 (`base.html`).
- **DRY**: helpers de traducción `t()`/`tf()`, dependencias de seguridad reutilizadas.
- **Nombrado claro** de módulos, rutas y variables (español descriptivo).
- **Comentarios mínimos** dejando que el código se explique por sí mismo.
- **Semántica HTML5** y accesibilidad básica (labels en formularios, `aria-*` en menús).
- **Rendimiento**: tablas paginables sencillas, consultas con `select` de SQLAlchemy filtradas por usuario en cliente.

---

## Pruebas

### Pruebas manuales recomendadas

| # | Escenario | Pasos |
|---|-----------|-------|
| 1 | Registro local | `/auth/register` → crear usuario → redirige a `/account` |
| 2 | Login local | `/auth/login` → entrar → redirige a `/account` |
| 3 | Login malo | Email/contraseña incorrecta → alerta de error |
| 4 | Compra | En `/shop` pulsar "Comprar" logueado → aparece en `/account/orders` |
| 5 | Compra sin login | Pulsar "Comprar" sin sesión → redirige a login |
| 6 | Envío de mensaje (cliente) | `/account/messages` → enviar → aparece en historial |
| 7 | Mensaje admin | Login como admin → `/admin/messages` → leído/responder/eliminar |
| 8 | Cambio de estado | Login admin → `/admin/orders/1` → cambiar estado |
| 9 | CRUD productos | Login admin → `/admin/products` → crear/editar/eliminar (con previsualización de archivo e imagen) |
| 10 | Protección admin | Login cliente → `/admin` → **403 Forbidden** |
| 11 | Cambio de idioma | Desplegable navbar → ES/EN/FR → todas las vistas traducidas |
| 12 | Responsive | Devolver con DevTools (F12) a 360px → menú hamburguesa, tablas con scroll |
| 13 | Recuperación de contraseña | `/auth/forgot-password` → introducir email → enlace → nueva contraseña → login |
| 14 | Encargo a medida | `/contact` con "Encargo a medida" → aparece en `/admin/commissions` → hilo con adjunto → cambio de estado |
| 15 | Paginación | En listados con +10 ítems → navegar páginas conservando filtros |

### Verificación de integridad de traducciones
Todos los ficheros `locales/*.json` deben tener las **mismas claves**. Si añades una clave nueva en un idioma, añádela a los tres. Las claves no encontradas devuelven el propio nombre de la clave (comportamiento *fail-safe*).

---

## Posibles mejoras futuras

- [ ] **Pagos reales** con Stripe/PayPal.
- [ ] **Carrito de compra** persistente en sesión.
- [ ] **Chat en tiempo real** con WebSockets (FastAPI los soporta nativamente).
- [ ] **Tests automatizados** con `pytest` + `TestClient`/`httpx`.
- [ ] **Dockerización** (`Dockerfile` + `docker-compose.yml`).
- [ ] **Panel de métricas** con gráficos (Chart.js).
- [ ] **2FA** para cuentas de administración.
- [ ] **Confirmación de email** en el registro.

---

## Licencia

Proyecto de demostración desarrollado para el cliente. *GH Diseños* es una marca de ejemplo.