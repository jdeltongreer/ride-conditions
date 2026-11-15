# Ride Conditions — project context

Personal ride-planning PWA. For each hour over 7 days it gives a **Good / Moderate / Poor** verdict for outdoor cycling, based on weather, wind, light, air quality and projected traffic, for several cities. It's used on desktop and installed on iPhone from Safari via GitHub Pages.

## Ground rules
- **Minimal complexity.** No build step, no framework, no npm dependencies, no backend. All app logic lives in `index.html`. Keep it that way unless a change can't be done otherwise. If it can't, say so and explain why before adding infrastructure.
- **No API keys.** Data comes only from Open-Meteo's free endpoints, called from the browser (CORS is open).
- **Show reasoning quantitatively.** When changing the scoring, give the before/after effect on concrete example hours, e.g. "clear weekday 2 AM: 72 → 80".
- After any change: run `python tests/smoke.py`, look at the screenshots in `tests/out/`, and **bump `VERSION` in `sw.js`** before deploying.

## Files
```
index.html            whole app: CSS, CFG, scoring, data, rendering, events
sw.js                 app-shell cache (cache-first + background refresh). Does NOT intercept API calls
manifest.webmanifest  PWA metadata
icons/                180 (apple-touch), 192, 512, maskable-512. Generated with PIL
tests/smoke.py        Playwright test with synthetic Open-Meteo data (no network needed)
README.md             deploy (GitHub Pages) + iPhone install steps
```

## Data flow (index.html)
`render()` → `getData(city)` → fetches the forecast and air-quality APIs → `build()` → one object per hour:
- local `date` / `hour` / weekday come from `Intl.DateTimeFormat` with the API's IANA `timezone`. The APIs use `timeformat=unixtime`, so DST is handled correctly.
- `sunEl` = solar elevation at mid-hour, from `solarEl()` (NOAA-style approximation)
- `light`: day ≥ 6° · low sun ≥ −0.833° · twilight ≥ −6° · dark
- `traffic` = `trafficR(hour, weekend)` (see the traffic model below)
- `scoreHour(h)` → `h.pen` (named penalties; a negative value is a bonus) and `h.score` (0–100, clamped)
- `verdict(h)` → `h.risk` (risk flags) and `h.vd = {v, stop, why}`

Days are grouped by local date. `sunTimes()` scans each local day minute by minute for dawn, sunrise, sunset and dusk. `bestWindow()` = the highest-average run of `S.win` consecutive hours. It skips hours that have already passed and any window containing a hard stop.

**Units:** everything is computed in **metric** (°C, km/h, mm, m). It's converted only at display time through `F.*`. `CFG` values are metric; the comments give °F/mph equivalents.

**State / storage:** `S` = `{cities, active, units, win, view, day}`. `localStorage` keys are prefixed `ride.`: `cities`, `active`, `units`, `win`, and `raw.<lat,lon>` (the last good API responses plus fetch time, used as the offline fallback). The in-memory cache lasts 30 minutes; auto-refresh is every 30 minutes and also runs on `visibilitychange`, since iOS pauses timers in the background.

## Scoring model (CFG, top of the script)
Each hour starts at 100.

| Factor | Rule (current values) |
|---|---|
| Feels-like temperature | outside 45–85°F: −3 per °C (≈ −1.7/°F), max −50 |
| Rain | −0.5 per % chance; extra −25 if ≥ 0.5 mm/h forecast |
| Wind | above 10 mph: −2 per km/h, max −35 |
| Gusts | above 20 mph: −1.5 per km/h, max −25 |
| US AQI | above 50: −0.5/pt, slope doubles above 100, max −60 |
| Light | dark −40, civil twilight −15 |
| UV | ≥ 8: −8 |
| Fog | visibility under 1 km: −20 |
| Thunderstorm | −50 |
| Traffic | linear bonus up to **+15** as r falls below 0.30; linear penalty up to **−20** as r rises above 0.55 |

**Verdict:** Good ≥ 75 · Moderate 50–74 · Poor < 50.

**Hard stops (`CFG.stop`, ⛔ forces Poor):** thunderstorm; ice or snow codes; AQI > 150; gusts ≥ 40 mph; feels-like ≤ 23°F or ≥ 100°F; rain ≥ 2.5 mm/h; visibility < 200 m.

**Combined risk (`CFG.risk`): any 2 of these 4 flags = ⛔:**
- 🌧️ weather: rain chance ≥ 50%, ≥ 0.25 mm/h forecast, visibility < 1 km, storm, or ice/snow
- 💨 gusts ≥ 30 mph (48 km/h)
- 🌙 low light: civil twilight or dark
- 🚗 traffic r ≥ 0.80

**Traffic model:** `TRAFFIC.weekday` / `TRAFFIC.weekend` give the typical share of daily volume per local hour (FHWA-style US urban shape). r = that share ÷ the weekday peak (5 PM). It's a **projection, not live data**: it doesn't account for holidays, events or specific roads.

### Decision log (the user's reasoning; keep it in mind)
- The comfort band was widened from 55–75°F to **45–85°F**. The user rides through a wide range.
- Traffic was added because the darkness penalty alone unfairly punished night riding: low traffic is a real benefit of riding at night.
- Weather, low light and high traffic are each a **major risk**, and any two together rule out a ride. **Gusts** were later split out as a fourth separate risk (previously they were part of weather).
- The high-traffic flag was raised from 60% to **80% of peak**. A cyclist can route around busy roads, but overall volume still predicts car interactions even on quiet routes. The traffic *score penalty* still starts at 55%.
- An open idea, not decided: lower the dark penalty from −40 to about −25 so clear, quiet late-night hours can reach Good. Ask before changing it.

## Gotchas
- **The phone layout hides table columns by position** (`th:nth-child(n)` rules inside `@media (max-width:700px)`). If you add, remove or reorder a table column, update those indexes and the detail row's `colspan` (currently 17). Columns: 1 Hour, 2 Verdict, 3 Sky, 4 Temp, 5 Rain, 6 Wind, 7 Gust, 8 From, 9 RH, 10 Cloud, 11 Vis, 12 UV, 13 AQI, 14 PM2.5, 15 Light, 16 Risks, 17 Traffic. On phones, 3, 8–12, 14, 15 and 17 are hidden.
- Each hour has a hidden detail row (`tr.det`) directly after it. The row-toggle code relies on `nextElementSibling`.
- The legend (`#legend`) is generated from `CFG`. Edit `CFG`, not the legend text.
- Air-quality data (CAMS) often runs out after about day 5. A missing value is `null` and simply doesn't count against the score. Keep scoring null-safe.
- "My location" is stored as a city with `here: true` and is replaced each time 📍 is tapped. It has no reverse-geocoded name, because Open-Meteo has no reverse geocoding.
- iPhone home-screen apps have **separate storage** from Safari, and `sw.js` changes only reach phones after `VERSION` is bumped.
- Never open `index.html` via `file://` for PWA testing. The service worker needs http(s). Use `python3 -m http.server`.

## Testing
```bash
pip install playwright && playwright install chromium
python tests/smoke.py        # from the repo root; screenshots go to tests/out/
```
Synthetic week: day 1 has a thunderstorm and rain in the afternoon, day 2 is windy with 40+ mph gusts at midday, day 3 has AQI 170 all day. The test checks verdicts, the service worker, the detail row, location, the offline fallback and page errors. Add a check when you add a rule. It has **never been run against live Open-Meteo** from the build environment, so check the first real-data load by hand.

## Deploy
GitHub Pages from `main` / root (see README). The address is `https://<user>.github.io/ride-conditions/`.

## Possible next steps (not started)
- Push alerts ("Good 3h window tomorrow", "⛔ smoke from 2 PM"). This needs a scheduled job plus Web Push, which works on iOS 16.4+ for home-screen apps. It would be the first backend piece.
- Logging of observed conditions (needs storage outside the browser).
- An on-page settings panel for `CFG` thresholds.
- Wind direction relative to a route; holiday-aware traffic.
