document.addEventListener("DOMContentLoaded", function () {
    // Auto-hide alerts after 5 seconds
    document.querySelectorAll(".alert-auto-hide").forEach(function (alert) {
        setTimeout(function () {
            alert.classList.add("fade");
            setTimeout(function () { alert.remove(); }, 300);
        }, 5000);
    });

    // Reveal on scroll
    var revealEls = document.querySelectorAll(".reveal");
    if (revealEls.length) {
        if ("IntersectionObserver" in window) {
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("reveal-visible");
                        io.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.12 });
            revealEls.forEach(function (el) { io.observe(el); });
        } else {
            revealEls.forEach(function (el) { el.classList.add("reveal-visible"); });
        }
    }

    // Unread notification badge (only when a navbar bell exists)
    var notifBadge = document.getElementById("notif-badge");
    if (notifBadge) {
        function refreshBadge() {
            fetch("/notifications/unread-count", { headers: { "Accept": "application/json" } })
                .then(function (r) { return r.ok ? r.json() : { count: 0 }; })
                .then(function (data) {
                    var n = parseInt(data.count, 10) || 0;
                    notifBadge.textContent = n > 99 ? "99+" : String(n);
                    if (n > 0) { notifBadge.classList.remove("d-none"); }
                    else { notifBadge.classList.add("d-none"); }
                })
                .catch(function () { notifBadge.classList.add("d-none"); });
        }
refreshBadge();
        setInterval(refreshBadge, 30000);

        // Mark a notification as read when the user clicks it (non-blocking),
        // then refresh the badge. Navigation continues natively.
        document.querySelectorAll(".notif-item[data-notif-id]").forEach(function (el) {
            el.addEventListener("click", function () {
                var id = el.getAttribute("data-notif-id");
                if (!id) return;
                fetch("/notifications/" + id + "/read", { method: "POST" })
                    .then(function () {
                        el.removeAttribute("data-notif-id");
                        el.classList.remove("notif-unread");
                        if (el.querySelector(".notif-dot")) { el.querySelector(".notif-dot").remove(); }
                        refreshBadge();
                    })
                    .catch(function () {});
            });
        });
    }

    // Product gallery: swap main image on thumbnail click + lightbox
    var galleryMain = document.getElementById("gallery-main");
    var zoomBtn = document.getElementById("gallery-zoom-btn");
    var lightbox = document.getElementById("lightbox");
    var lightboxImg = document.getElementById("lightbox-img");
    var lightboxClose = document.getElementById("lightbox-close");

    if (galleryMain && lightbox) {
        document.querySelectorAll(".gallery-thumb").forEach(function (thumb) {
            var swap = function () {
                document.querySelectorAll(".gallery-thumb").forEach(function (t) { t.classList.remove("active"); });
                thumb.classList.add("active");
                galleryMain.src = "/uploads/" + thumb.getAttribute("data-src");
                if (lightboxImg) lightboxImg.src = galleryMain.src;
            };
            thumb.addEventListener("click", swap);
            thumb.addEventListener("keydown", function (e) {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); swap(); }
            });
        });

        var openZoom = function () {
            if (lightboxImg) lightboxImg.src = galleryMain.src;
            lightbox.classList.add("open");
            document.body.style.overflow = "hidden";
        };
        if (zoomBtn) zoomBtn.addEventListener("click", openZoom);

        if (lightboxClose) lightboxClose.addEventListener("click", function () {
            lightbox.classList.remove("open");
            document.body.style.overflow = "";
        });
        lightbox.addEventListener("click", function (e) {
            if (e.target === lightbox) {
                lightbox.classList.remove("open");
                document.body.style.overflow = "";
            }
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && lightbox && lightbox.classList.contains("open")) {
                lightbox.classList.remove("open");
                document.body.style.overflow = "";
            }
        });
    }
});
// ---- Cookie consent banner ----
(function () {
    var banner = document.getElementById("cookie-banner");
    if (!banner) {
        return;
    }
    function setConsent(value) {
        document.cookie = "cookie_consent=" + value + ";max-age=31536000;path=/;SameSite=Lax";
        banner.remove();
    }
    banner.querySelectorAll("[data-cookie-action]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            setConsent(btn.getAttribute("data-cookie-action") === "accept" ? "accepted" : "rejected");
        });
    });
})();

// ---- Star input + reviews slider (home) ----
document.addEventListener("DOMContentLoaded", function () {
    var input = document.getElementById("star-input");
    if (input) {
        var ratingField = document.getElementById("rating");
        var stars = input.querySelectorAll(".star-option");
        function refresh(v) {
            stars.forEach(function (s) {
                s.classList.toggle("bi-star-fill", parseInt(s.dataset.value) <= v);
                s.classList.toggle("bi-star", parseInt(s.dataset.value) > v);
                s.classList.add("text-warning");
            });
        }
        stars.forEach(function (s) {
            s.addEventListener("click", function () {
                var v = parseInt(s.dataset.value);
                if (ratingField) ratingField.value = v;
                refresh(v);
            });
            s.addEventListener("keydown", function (e) {
                if (e.key === " " || e.key === "Enter") {
                    e.preventDefault();
                    var v = parseInt(s.dataset.value);
                    if (ratingField) ratingField.value = v;
                    refresh(v);
                }
            });
        });
        refresh(5);
    }

    var widget = document.getElementById("review-widget");
    if (widget) {
        var slides = widget.querySelectorAll(".review-slide");
        var counter = document.getElementById("review-counter");
        var idx = 0;
        var total = slides.length;
        function show(n) {
            slides.forEach(function (s, i) { s.hidden = i !== n; });
            if (counter) counter.textContent = (n + 1) + " / " + total;
        }
        var prev = widget.querySelector(".review-prev");
        var next = widget.querySelector(".review-next");
        if (next) next.addEventListener("click", function () { idx = (idx + 1) % total; show(idx); });
        if (prev) prev.addEventListener("click", function () { idx = (idx - 1 + total) % total; show(idx); });
    }
});
