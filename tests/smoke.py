"""Offline smoke test: serves the app locally, replaces Open-Meteo with synthetic data,
and checks the verdict logic, PWA install, offline fallback and phone layout.

    pip install playwright && playwright install chromium
    python tests/smoke.py            # from the repo root

Synthetic week (local Pasadena time, starting today):
  day 1  thunderstorm 3-5 PM, 80% rain 1-6 PM   -> hard stops
  day 2  windy all day, 40+ mph gusts 12-5 PM   -> gust hard stops
  day 3  AQI 170 all day                        -> no rideable window
Screenshots go to tests/out/.
"""
import asyncio, functools, http.server, json, math, os, socketserver, threading, time
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tests', 'out'); os.makedirs(OUT, exist_ok=True)

def synthetic():
    now = int(time.time()); t0 = now - now % 86400 + 8 * 3600   # ~LA midnight (PST)
    if t0 > now: t0 -= 86400
    N = 168; ts = [t0 + i * 3600 for i in range(N)]
    keys = ["temperature_2m", "apparent_temperature", "relative_humidity_2m", "precipitation_probability", "precipitation",
            "weather_code", "cloud_cover", "visibility", "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "uv_index"]
    H = {k: [] for k in keys}; H["time"] = ts
    for i in range(N):
        d, h = divmod(i, 24)
        temp = 12 + 8 * math.sin((h - 9) / 24 * 2 * math.pi)
        storm = d == 1 and h in (15, 16)
        H["temperature_2m"].append(temp); H["apparent_temperature"].append(temp - 1)
        H["relative_humidity_2m"].append(50); H["cloud_cover"].append(20); H["visibility"].append(20000)
        H["precipitation_probability"].append(80 if d == 1 and 13 <= h <= 17 else 5)
        H["precipitation"].append(3.0 if storm else 0); H["weather_code"].append(95 if storm else 1)
        H["wind_speed_10m"].append(8 + (30 if d == 2 else 0))
        H["wind_gusts_10m"].append(15 + (55 if d == 2 and 12 <= h <= 16 else 0))
        H["wind_direction_10m"].append(270); H["uv_index"].append(4)
    fc = {"timezone": "America/Los_Angeles", "hourly": H}
    aq = {"hourly": {"time": ts[:120], "us_aqi": [170 if i // 24 == 3 else 40 for i in range(120)],
                     "pm2_5": [10] * 120, "pm10": [15] * 120, "ozone": [60] * 120}}
    return fc, aq

def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Quiet, directory=ROOT)
    class Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True; daemon_threads = True
    srv = Srv(("127.0.0.1", 0), h)   # any free port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

async def main():
    fc, aq = synthetic(); srv = serve(); fails = []; port = srv.server_address[1]
    def check(name, ok, detail=''):
        print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail else ''))
        if not ok: fails.append(name)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(**p.devices['iPhone 13'], permissions=["geolocation"],
                                  geolocation={"latitude": 40.6993, "longitude": -111.8434})
        online = {"v": True}; errs = []
        async def route(r):
            if not online["v"]: return await r.abort()
            body = aq if "air-quality" in r.request.url else fc
            await r.fulfill(status=200, content_type="application/json", body=json.dumps(body),
                            headers={"access-control-allow-origin": "*"})
        await ctx.route(lambda u: "open-meteo" in u, route)
        pg = await ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"http://127.0.0.1:{port}/"); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=f"{OUT}/phone-top.png")

        best = await pg.locator(".ovbest").all_inner_texts()
        check("7 day rows", len(best) == 7, str(len(best)))
        check("AQI 170 day has no window", best[3] == 'no rideable window left', best[3])
        check("SW active", await pg.evaluate("navigator.serviceWorker.getRegistration().then(r=>!!(r&&r.active))"))
        await pg.click(".ovlab[data-day='1']"); await pg.wait_for_timeout(200)
        stops = await pg.locator("td .score:has-text('⛔')").count()
        check("storm day has hard stops", stops >= 2, f"{stops} stops")
        await pg.click("tr.hr:nth-of-type(13)"); await pg.wait_for_timeout(150)
        check("tap opens detail row", await pg.locator("tr.det.open").count() == 1)
        await pg.screenshot(path=f"{OUT}/phone-day1.png", full_page=True)
        await pg.click("#loc"); await pg.wait_for_timeout(800)
        chips = await pg.locator(".chip").all_inner_texts()
        check("location chip added", chips[0].startswith('My location'), chips[0].split('\n')[0])
        online["v"] = False; await ctx.set_offline(True)
        await pg.reload(); await pg.wait_for_timeout(1200)
        stamp = await pg.inner_text("#stamp")
        check("offline shows cached data", stamp.startswith("Offline"), stamp)
        check("no page errors", not errs, '; '.join(errs))
        await b.close()
    srv.shutdown()
    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'} · screenshots in tests/out/")
    raise SystemExit(1 if fails else 0)

asyncio.run(main())
