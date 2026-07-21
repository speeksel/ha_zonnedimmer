#!/usr/bin/env python3
"""Zonnedimmer login diagnostic met aiohttp - repliceert de HA-integration exact.

Installeer aiohttp:  pip3 install aiohttp
Gebruik:
    export ZONNEDIMMER_EMAIL="jouw@email.nl"
    export ZONNEDIMMER_PASSWORD="jouwWachtwoord"
    python3 zonnedimmer-login-test.py
"""
import asyncio
import os
import re
import sys

try:
    import aiohttp
except ImportError:
    print("Installeer aiohttp:  pip3 install aiohttp")
    sys.exit(2)

BASE_URL = os.environ.get("BASE_URL", "https://app.zonnedimmer.nl").rstrip("/")
EMAIL = os.environ.get("ZONNEDIMMER_EMAIL")
PASSWORD = os.environ.get("ZONNEDIMMER_PASSWORD")
if not EMAIL or not PASSWORD:
    print("Set ZONNEDIMMER_EMAIL en ZONNEDIMMER_PASSWORD env vars")
    sys.exit(2)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
META_CSRF = re.compile(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', re.I)
META_AUTH = re.compile(r'<meta\s+name="user-authenticated"\s+content="([^"]+)"', re.I)


async def main():
    # Test BOTH de standaard cookie jar en unsafe=True (ongeacht domein).
    for label, jar in [
        ("default CookieJar", aiohttp.CookieJar()),
        ("CookieJar(unsafe=True)", aiohttp.CookieJar(unsafe=True)),
    ]:
        print(f"\n========== Test met {label} ==========")
        async with aiohttp.ClientSession(
            cookie_jar=jar,
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": UA},
        ) as session:
            # 1. GET /login
            print("\n--- 1. GET /login ---")
            async with session.get(f"{BASE_URL}/login") as r:
                html = await r.text()
                print(f"status={r.status} url={r.url}")
                cookies_after_get = dict(session.cookie_jar)
            m = META_CSRF.search(html)
            if not m:
                print("FAIL: geen CSRF-token gevonden")
                continue
            csrf = m.group(1)
            print(f"CSRF gevonden (lengte {len(csrf)})")

            # 2. POST /login
            print("\n--- 2. POST /login (Referer+Origin) ---")
            payload = {"_token": csrf, "email": EMAIL, "password": PASSWORD}
            headers = {"Referer": f"{BASE_URL}/login", "Origin": BASE_URL}
            async with session.post(
                f"{BASE_URL}/login",
                data=payload,
                headers=headers,
                allow_redirects=True,
            ) as r:
                body = await r.text()
                print(f"status={r.status} final_url={r.url}")
                print(f"body_len={len(body)}")
                print("Set-Cookie in response headers:",
                      r.headers.getall("Set-Cookie", ["(geen)"]))

            # 3. GET /dashboard/settings
            print("\n--- 3. GET /dashboard/settings ---")
            async with session.get(
                f"{BASE_URL}/dashboard/settings",
                headers={"Referer": f"{BASE_URL}/dashboard"},
                allow_redirects=True,
            ) as r:
                shtml = await r.text()
                print(f"status={r.status} final_url={r.url}")
            m2 = META_AUTH.search(shtml)
            auth = m2.group(1) if m2 else "(meta niet gevonden)"
            print(f"user-authenticated = {auth}")
            print(f"sessie-cookies: {[c.key for c in session.cookie_jar]}")

            if auth == "1":
                print(f">>> SUCCES met {label} - flow werkt in aiohttp!")
                return

    print("\n>>> FAIL: geen van beide cookie-jars leverde authenticated=1")
    print("    -> verschil met curl wijst op aiohttp-cookie/redirect-gedrag")


asyncio.run(main())
