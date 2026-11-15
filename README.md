# Ride Conditions (PWA)

Static web app. No backend, no API keys. Data comes from Open-Meteo (forecast, air quality, geocoding), called directly from the browser.

```
index.html             app (all logic + CFG scoring block)
manifest.webmanifest   name, icons, standalone display
sw.js                  offline app-shell cache
icons/                 home-screen icons
```

## Deploy to GitHub Pages
```bash
cd ride-pwa
git init && git add . && git commit -m "Ride Conditions PWA"
gh repo create ride-conditions --public --source=. --push
gh api -X POST repos/{owner}/ride-conditions/pages -f "source[branch]=main" -f "source[path]=/"
```
The site comes up at `https://<you>.github.io/ride-conditions/` in about a minute.
(GitHub Pages on a private repo needs a paid plan. The repo has no secrets, so public is fine.)

## Install on iPhone
1. Open the URL in **Safari**.
2. Share → **Add to Home Screen** → Add.
3. Launch it from the icon, then re-add your cities. Home-screen apps have storage separate from Safari.

## Updating
Edit, then **bump `VERSION` in `sw.js`** (e.g. `ride-v2`), commit and push. The phone picks up the new version on the next launch after it has fetched it, so it may take two opens.

## Local testing
`python3 -m http.server 8000` in this folder, then open http://localhost:8000. The service worker needs http(s), not a file:// path.
