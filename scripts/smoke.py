"""End-to-end smoke test over every route using the real ASGI app."""
import sys
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from app.main import app

PUBLIC = ["/", "/login", "/register", "/forgot-password", "/reset-password",
          "/verify-email", "/demo", "/healthz", "/api/health", "/api/languages",
          "/static/css/nirvaan.css", "/static/js/nirvaan.js",
          "/static/manifest.webmanifest", "/static/offline.html"]

PROTECTED = ["/dashboard", "/talk", "/check", "/reflect", "/learn", "/market",
             "/journey", "/family", "/privacy", "/settings", "/offline",
             "/batch", "/decision-readiness", "/explain", "/shield", "/help",
             "/responsible-ai"]

fails = []

with TestClient(app, follow_redirects=False) as client:
    print("=== PUBLIC ===")
    for path in PUBLIC:
        r = client.get(path)
        ok = r.status_code in (200, 301, 303, 503)
        print(f"  {r.status_code}  {path}")
        if not ok:
            fails.append((path, r.status_code, r.text[:300]))

    print("\n=== PROTECTED (anonymous -> expect 303 to /login) ===")
    for path in PROTECTED:
        r = client.get(path)
        ok = r.status_code == 303 and "/login" in r.headers.get("location", "")
        print(f"  {r.status_code} -> {r.headers.get('location','')}  {path}")
        if not ok:
            fails.append((path, r.status_code, "expected 303 to /login"))

    print("\n=== LOGIN FLOW ===")
    page = client.get("/login")
    csrf = client.cookies.get("nirvaan_csrf")
    print("  csrf cookie issued:", bool(csrf))

    r = client.post("/login", data={"email": "priya@nirvaan.local",
                                    "password": "NirvaanDemo2026", "_csrf": csrf,
                                    "next": "/dashboard"})
    print(f"  login status={r.status_code} -> {r.headers.get('location','')}")
    if r.status_code != 303:
        fails.append(("/login POST", r.status_code, r.text[:500]))

    print("\n=== PROTECTED (signed in) ===")
    for path in PROTECTED:
        r = client.get(path)
        print(f"  {r.status_code}  {path}  ({len(r.content)} bytes)")
        if r.status_code != 200:
            fails.append((path, r.status_code, r.text[:400]))

    print("\n=== RBAC: admin page as normal user ===")
    r = client.get("/admin")
    print(f"  /admin as USER -> {r.status_code} (expect 403)")
    if r.status_code != 403:
        fails.append(("/admin as USER", r.status_code, "expected 403"))

    print("\n=== CSRF: POST without token ===")
    r = client.post("/api/language", data={"language": "hi"})
    print(f"  no-token POST -> {r.status_code} (expect 403)")
    if r.status_code != 403:
        fails.append(("csrf", r.status_code, "expected 403"))

    print("\n=== LANGUAGE SWITCH ===")
    csrf = client.cookies.get("nirvaan_csrf")
    r = client.post("/api/language", data={"language": "ta", "_csrf": csrf, "next": "/dashboard"})
    print(f"  switch to ta -> {r.status_code}")
    r = client.get("/dashboard")
    has_tamil = "தமிழ்" in r.text or 'lang="ta"' in r.text
    print(f"  dashboard renders Tamil: {has_tamil}")
    if not has_tamil:
        fails.append(("language switch", 0, "Tamil not rendered"))

    print("\n=== LOGOUT ===")
    csrf = client.cookies.get("nirvaan_csrf")
    r = client.post("/logout", data={"_csrf": csrf})
    print(f"  logout -> {r.status_code}")
    r = client.get("/dashboard")
    print(f"  dashboard after logout -> {r.status_code} (expect 303)")
    if r.status_code != 303:
        fails.append(("post-logout", r.status_code, "expected 303"))

    print("\n=== ADMIN LOGIN + CONSOLE ===")
    client.get("/login")
    csrf = client.cookies.get("nirvaan_csrf")
    r = client.post("/login", data={"email": "admin@nirvaan.local",
                                    "password": "QuietLotus7Harbour", "_csrf": csrf})
    print(f"  admin login -> {r.status_code}")
    r = client.get("/admin")
    print(f"  /admin as ADMIN -> {r.status_code}")
    if r.status_code != 200:
        fails.append(("/admin as ADMIN", r.status_code, r.text[:400]))
    r = client.get("/api/providers")
    print(f"  /api/providers as ADMIN -> {r.status_code}")

print("\n" + "=" * 60)
if fails:
    print(f"FAILURES: {len(fails)}")
    for path, code, detail in fails:
        print(f"\n  {path} [{code}]\n    {detail}")
    sys.exit(1)
print("ALL SMOKE CHECKS PASSED")
