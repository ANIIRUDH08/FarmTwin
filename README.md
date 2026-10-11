# FarmTwin – offline web app (PC + phone)

Runs Streamlit inside the browser, so there is no server. After one visit with internet,
it opens and works offline. The AI explanation works whenever the device is online.

## 1. Add your two model files
Copy these from your original FarmTwin folder into this folder (next to `index.html`):
- `crop_model.joblib`
- `Crop_recommendation.csv`   (used automatically if the .joblib can't be loaded in the browser)

## 2. Add your Gemini key
Open `api_key.py` and paste the key. Everyone who opens the site can see this file,
so in Google AI Studio / Cloud Console limit the key to your website address
(HTTP referrers) and set a spending limit.

## 3. Test on your PC
    python -m http.server 8000
Open http://localhost:8000 in Chrome or Edge.

## 4. Publish it (free static hosting)
Upload this whole folder to GitHub Pages, Netlify (drag and drop) or Cloudflare Pages.
It must be served over https (those all do this). Share the link.

## 5. Make it work offline
Open the link ONCE with internet and wait for the app to finish loading (first load is
large and can take a minute or two). Then:
- Android (Chrome): menu -> Install app / Add to Home screen
- iPhone (Safari): Share -> Add to Home Screen
- PC (Chrome/Edge): install icon in the address bar
After that it opens with no connection. Offline you get the simulation, charts, crop
recommendation and season advice; the AI box says it needs internet.

## Check that offline really works
In Chrome: press F12 -> Application -> Cache Storage -> `farmtwin-v1`. You should see
files from this site AND from cdn.jsdelivr.net. Then Network tab -> tick "Offline" -> reload.

## Updating the site later
Change `CACHE_VERSION` in `sw.js` (for example to `farmtwin-v2`) before re-uploading,
so devices fetch the new files.
