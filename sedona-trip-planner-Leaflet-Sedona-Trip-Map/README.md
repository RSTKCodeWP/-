# Sedona Trip Planner

An interactive satellite map with mountain biking, electric dirt bike (OHV), and hiking pins for a week-long camping trip to Sedona, Arizona.

**Live site:** Once deployed to GitHub Pages, this will be at `https://<your-username>.github.io/sedona-trip-planner/`

## Features

- Full-screen satellite map (Google satellite tiles, hybrid + pure satellite + terrain modes)
- 35 hand-curated pins across 5 categories: Basecamp, Bike Shop, Mountain Bike, E-Dirt Bike (OHV), Hike — with drive time + distance from basecamp on every activity pin
- Click any pin → detailed modal with description, field notes, embedded POV YouTube video, and external links (USFS, AllTrails, Trailforks, directions)
- Legend doubles as a category filter — click "Mountain Bike" to zoom to all MTB pins
- Editorial design with custom fonts (Bebas Neue + Fraunces + DM Mono)
- Mobile responsive

## Project structure

```
sedona-trip-planner/
├── index.html      # Page structure
├── style.css       # All styling
├── app.js          # Leaflet map + modal logic
├── data.js         # All pin data (edit this to update locations/videos/descriptions)
├── .nojekyll       # Tells GitHub Pages to serve files as-is
├── README.md
└── LICENSE
```

## Editing content

All locations, descriptions, YouTube videos, and links live in **`data.js`**. To add or change a pin, edit the `PINS` array. Each pin has:

```js
{
  id: 'unique-slug',
  category: 'mtb' | 'ohv' | 'hike' | 'basecamp' | 'shop',
  name: 'Display Name',
  short: 'Short subtitle for popup',
  lat: 34.xxxx,
  lng: -111.xxxx,
  difficulty: 'Intermediate (Blue)',
  distance: '6.1 mi loop',
  description: 'Long HTML description for modal',
  tips: ['Field note 1', 'Field note 2'],
  youtube: 'https://www.youtube.com/embed/VIDEO_ID',  // use the /embed/ URL
  youtubeTitle: 'Video caption',
  links: [
    { label: 'Trailforks', url: 'https://...' }
  ]
}
```

## Deploy to GitHub Pages

### 1. Create a new GitHub repo

```bash
# Initialize git locally
cd sedona-trip-planner
git init
git add .
git commit -m "Initial Sedona trip planner"

# Create the repo on GitHub (via the web UI or `gh` CLI) and push
git branch -M main
git remote add origin https://github.com/<your-username>/sedona-trip-planner.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to your repo on GitHub
2. **Settings → Pages**
3. Under "Build and deployment", set:
   - **Source:** Deploy from a branch
   - **Branch:** `main` / `/ (root)`
4. Click Save

GitHub will build and deploy. Your site will be live at:
```
https://<your-username>.github.io/sedona-trip-planner/
```

It usually takes 1-2 minutes the first time.

### 3. Custom domain (optional)

If you want to use a custom domain (e.g. `sedona.yourdomain.com`):

1. In **Settings → Pages**, add your custom domain
2. Create a `CNAME` file in the repo with just your domain on one line
3. Add a CNAME DNS record at your domain registrar pointing to `<your-username>.github.io`

## Local preview

You can preview locally with any static server:

```bash
# Python 3
python3 -m http.server 8000

# OR Node
npx serve .
```

Then open `http://localhost:8000` in your browser.

## Tile attribution / Google note

This map uses Google's public satellite tile endpoints (`mt0-3.google.com/vt/lyrs=y`). For personal/non-commercial use this works fine, but for production or commercial use you should switch to the official **Google Maps JavaScript API** (with an API key) or use an alternative satellite tile provider like **Esri World Imagery** or **Mapbox Satellite**.

To swap to Esri (no API key required, fully production-safe), edit `app.js` and replace the `googleSatHybrid` tile layer with:

```js
const esriSat = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  { attribution: 'Tiles &copy; Esri', maxZoom: 19 }
);
```

## Stack

- [Leaflet](https://leafletjs.com/) for the map
- Google satellite tiles (via public tile endpoints)
- No build step — pure HTML/CSS/JS

## License

MIT — see [LICENSE](LICENSE).
