# ⚙️ TerraForge Studio - Settings Guide

Complete guide to configuring TerraForge Studio settings.

---

## 🚀 Quick Setup

### First Time Setup

When you first open TerraForge Studio, you'll see a **Setup Wizard** that guides you through:

1. **Language Selection** - Choose English or Русский
2. **API Keys** - Optionally add premium data source keys
3. **Default Engine** - Select your primary export target (UE5, Unity, Generic)

**Note:** You can skip all steps and use free data sources (OpenStreetMap + SRTM).

---

## 🔑 Managing API Keys

### Accessing Settings

Click the **"Settings"** button in the top-right corner of the application.

### Data Sources Tab

Configure credentials for premium geospatial data sources:

#### 1. Sentinel Hub (Satellite Imagery)

**What it provides:**
- High-resolution satellite imagery (10-60m)
- RGB, NIR, NDVI bands
- Temporal series analysis

**How to get API keys:**
1. Sign up at https://www.sentinel-hub.com/
2. Create a new configuration
3. Copy Client ID, Client Secret, Instance ID
4. Paste into TerraForge Settings
5. Click "Test Connection"

**Required fields:**
- Client ID
- Client Secret
- Instance ID (optional)

#### 2. OpenTopography (High-Resolution DEMs)

**What it provides:**
- LiDAR elevation data (0.5-2m in select regions)
- Global SRTM data (30m)
- ASTER GDEM (30m)

**How to get API key:**
1. Register at https://opentopography.org/
2. Go to MyOpenTopo → Request API Key
3. Copy your API key
4. Paste into TerraForge Settings
5. Click "Test Connection"

**Required fields:**
- API Key

#### 3. Azure Maps (Vector + Elevation)

**What it provides:**
- Vector data (roads, buildings, POI)
- Elevation API
- Routing services

**How to get subscription key:**
1. Create Azure account at https://azure.microsoft.com/
2. Create Azure Maps resource
3. Get subscription key from "Authentication" section
4. Paste into TerraForge Settings
5. Click "Test Connection"

**Required fields:**
- Subscription Key

#### 4. Google Earth Engine (Advanced)

**What it provides:**
- Massive geospatial datasets
- Land cover classification
- Temporal analysis

**Setup (Advanced):**
Google Earth Engine requires a service account and JSON key file. See [Google Earth Engine docs](https://developers.google.com/earth-engine/guides/service_account) for setup.

**Note:** This is an advanced data source. We recommend starting with Sentinel Hub or OpenTopography.

---

## 🔐 Security

### How API Keys Are Stored

**Encryption:**
- All API keys are **encrypted** using Fernet (symmetric encryption)
- The encryption key is generated at random on first use and stored in
  `data/.secret_key`, created with `0600` permissions (never commit this!)
- Keys encrypted before saving to `data/settings.json`

Both paths are configurable, so the files can live outside the working
directory:

```bash
SETTINGS_STORAGE_FILE=data/settings.json
SECRET_KEY_FILE=data/.secret_key
```

> **⚠️ Upgrading from a build before the random key**
>
> The key used to be derived from a password and salt hardcoded in the source,
> so every install shared one key and anyone with a copy of `settings.json`
> could decrypt it without the key file. If your `data/.secret_key` was created
> by such a build, the credentials in it should be considered exposed:
>
> ```bash
> rm data/.secret_key        # a fresh random key is generated on next start
> ```
>
> Then re-enter each API key in the settings UI, and rotate any key that was
> stored under the old scheme at the provider that issued it.

**Best Practices:**
- Never share your `data/.secret_key` file
- Back it up: without it, stored credentials cannot be decrypted
- Add `data/` to `.gitignore`
- Use environment variables in production
- Rotate keys regularly

### Secret Visibility

- API keys are **hidden by default** (shown as `****abcd`)
- Click the "eye" icon to temporarily reveal
- Secrets never logged or sent to analytics

---

## ⚙️ Generation Defaults

### Settings Tab: Generation

**Default Resolution**
- Range: 512 - 8192 pixels
- Recommended: 2048 (balanced quality/speed)
- UE5 optimized: 2017, 4033
- Unity optimized: 2049, 4097

**Max Area (km²)**
- Range: 1 - 500 km²
- Default: 100 km²
- Larger areas require more memory and time

**Elevation Source Priority**
- Drag to reorder sources
- First available source will be used
- Recommended: OpenTopography → SRTM → ASTER

**Default Features:**
- Roads - Extract from OpenStreetMap
- Buildings - Extract building footprints
- Vegetation - Generate based on land use
- Weightmaps - Auto-generate material layers

**Processing:**
- Parallel Processing - Use multiple CPU cores
- Max Workers - Number of parallel tasks (1-16)

---

## 🎮 Export Profiles

### Unreal Engine 5 Profile

**Default Landscape Size:**
- 1009 - Small (1 km²)
- 2017 - Medium (4 km²) **← Recommended**
- 4033 - Large (16 km²)
- 8129 - Huge (64 km²)

**Heightmap Format:**
- `16bit_png` - PNG format (recommended)
- `raw` - RAW binary format

**Export Options:**
- **Weightmaps** - Generate material layers (R/G/B/A for rock/grass/dirt/sand)
- **Splines** - Road splines for UE5
- **Import Script** - Auto-generate Python import script

### Unity Profile

**Default Terrain Size:**
- 513 - Small
- 1025 - Medium
- 2049 - Large **← Recommended**
- 4097 - Huge

**Heightmap Format:**
- `raw` - RAW 16-bit (recommended for Unity)
- `16bit_png` - PNG format (alternative)

**Export Options:**
- **Splatmaps** - Terrain texture layers
- **Prefabs** - GameObject placement data
- **Import Script** - C# Editor script

### Generic Profile

**Formats to Export:**
- GLTF/GLB - 3D mesh format
- GeoTIFF - Georeferenced raster
- OBJ - Universal 3D format (optional)

**GLTF Options:**
- Binary format (GLB) - Recommended for smaller file size
- Separate files (GLTF + BIN) - Better for editing

---

## 🎨 UI & Language

### Language

- **English** - Full support
- **Русский (Russian)** - Full support
- Changes apply immediately

### Theme

- **Light** - Default bright theme
- **Dark** - Dark mode (coming soon)
- **Auto** - Follow system preference (coming soon)

### Display Options

- **Show Tooltips** - Helpful hints on hover
- **Show Tutorial** - First-time tutorial overlays
- **Compact Mode** - Reduced spacing for smaller screens
- **Default Map View** - Start with 2D map or 3D preview

---

## 💾 Storage & Cache

### Cache Settings

**Cache Directory:**
- Default: `./cache`
- Stores downloaded elevation data and imagery
- Can be changed to any writable path

**Cache Behavior:**
- **Enable Cache** - Reuse downloaded data (recommended)
- **Expiry** - Auto-delete cached data after N days (1-365)
- **Auto-cleanup** - Remove old generated projects

**Output Directory:**
- Default: `./output`
- Where generated terrains are saved
- Each terrain gets its own subfolder

### Manual Cache Management

**Clear Cache Button:**
- Deletes all cached elevation/imagery data
- Frees disk space
- Next generation will re-download data

**Clear Old Projects:**
- Removes generated terrains older than threshold
- Configurable days (default: 30)
- Keeps recent projects

---

## 📤 Import/Export Settings

### Export Your Settings

1. Go to Settings → scroll to bottom
2. Click **"Export Settings"**
3. Choose:
   - **Without credentials** - Safe for sharing (recommended)
   - **With credentials** - Full backup (encrypted)
4. Save `terraforge-settings.json` file

### Import Settings

1. Go to Settings → scroll to bottom
2. Click **"Import Settings"**
3. Select `terraforge-settings.json` file
4. Confirm import
5. Settings applied immediately

**Use Cases:**
- Transfer settings to another computer
- Share configuration with team (without credentials)
- Backup before reset

---

## 🔄 Resetting Settings

### Reset to Defaults

**Warning:** This will delete all configured API keys!

1. Go to Settings → scroll to bottom
2. Click **"Reset to Defaults"**
3. Confirm action
4. All settings restored to factory defaults
5. Will show Setup Wizard again

---

## 🧪 Testing Connections

### Test Data Source

For each data source in **Data Sources** tab:

1. Configure credentials
2. Click **"Test Connection"**
3. Wait for result:
   - ✅ Green check - Connection successful
   - ❌ Red X - Connection failed (check key)

**What's tested:**
- API key validity
- Network connectivity
- Service availability
- Quota limits

---

## 💡 Best Practices

### For Free Users

**Use:**
- OpenStreetMap (roads, buildings) - Always free
- SRTM (elevation, 30-90m) - Always free

**Skip:**
- Premium API keys (unless you need higher resolution)

### For Professional Use

**Recommended Setup:**
1. **OpenTopography** - Best free high-res DEMs
2. **Sentinel Hub** - Best satellite imagery
3. **Azure Maps** - Additional vector data

**Benefits:**
- Higher resolution terrains
- Better texture quality
- More detailed features

### Security Tips

1. **Never commit** `data/` folder to git
2. **Add to .gitignore:**
   ```
   data/
   .secret_key
   *.enc
   ```
3. **Use environment variables** in production
4. **Rotate API keys** regularly
5. **Export settings** for backup (without credentials)

---

## 🆘 Troubleshooting

### API Keys Not Saving

**Check:**
- `data/` directory exists and is writable
- No permission errors in console
- Not using special characters in keys

**Fix:**
```bash
# Ensure data directory exists
mkdir -p data
chmod 755 data
```

### Connection Tests Fail

**Common issues:**
1. **Invalid API key** - Double-check key from provider
2. **Network firewall** - Check firewall/proxy settings
3. **Quota exceeded** - Check your usage limits
4. **Service down** - Check provider status page

### Settings Not Persisting

**Check:**
- File `data/settings.json` exists
- No errors in browser console
- Backend is running and accessible

**Fix:**
```bash
# Check backend logs
poetry run uvicorn realworldmapgen.api.main:app --log-level debug

# Look for errors when saving settings
```

### Encryption Errors

Decryption returns an empty string rather than raising, so a corrupted or
mismatched key shows up as blank credentials instead of a crash.

If you see decryption errors, or credentials come back empty after restoring a
backup, the key no longer matches the stored data:

```bash
# Delete encryption key (will need to re-enter all keys)
rm data/.secret_key

# Restart application
```

A new random key is generated on the next start; existing values in
`settings.json` become undecryptable, so re-enter them in the settings UI.

---

## 📝 Settings File Format

Settings are stored in `data/settings.json`:

```json
{
  "user_name": null,
  "credentials": {
    "sentinelhub": {
      "enabled": false,
      "client_id": "encrypted_base64_string_here"
    },
    "opentopography": {
      "enabled": true,
      "api_key": "encrypted_base64_string_here"
    }
  },
  "generation": {
    "default_resolution": 2048,
    "max_area_km2": 100.0,
    "elevation_source_priority": ["opentopography", "srtm"]
  },
  "export_profiles": {
    "default_engine": "unreal5",
    "unreal5": {
      "default_landscape_size": 2017,
      "export_weightmaps": true
    }
  },
  "ui": {
    "language": "en",
    "theme": "light"
  },
  "version": "1.0.0",
  "first_run": false
}
```

**Note:** API keys are encrypted in the actual file.

---

## 🎓 Advanced: Programmatic Access

### Via Python API

```python
from realworldmapgen.settings import settings_manager

# Load settings
settings = settings_manager.get()

# Update
settings.generation.default_resolution = 4096
settings_manager.save()

# Test connection
success, error = settings_manager.test_connection('opentopography')
print(f"OpenTopography: {'✓' if success else '✗'} {error or 'OK'}")
```

### Via REST API

```bash
# Get settings
curl http://localhost:8000/api/settings/

# Update settings
curl -X POST http://localhost:8000/api/settings/ \
  -H "Content-Type: application/json" \
  -d '{"generation": {"default_resolution": 4096}}'

# Test connection
curl -X POST http://localhost:8000/api/settings/test-connection/opentopography
```

---

## 📊 Comparison: Free vs Premium

| Feature | Free (OSM+SRTM) | Premium (All Sources) |
|---------|-----------------|----------------------|
| **Elevation** | 30-90m | 0.5-30m (LiDAR) |
| **Imagery** | ❌ No | ✅ 10-60m RGB/NIR |
| **Roads** | ✅ OpenStreetMap | ✅ OSM + Azure |
| **Buildings** | ✅ OSM footprints | ✅ OSM + heights |
| **Setup** | Zero config | API keys needed |
| **Cost** | Free forever | Varies by usage |
| **Quality** | Good | Excellent |

**Recommendation:** Start with free sources, add premium keys later if you need higher quality.

---

## 🎉 You're Ready!

Settings are now configured. Start generating terrains!

**Next Steps:**
- Return to main app
- Select area on map
- Generate your first terrain
- Import to UE5/Unity

**Need Help?**
- Check main [README.md](../README.md)
- See [API Examples](API_EXAMPLES.md)
- Visit Settings → Help

---

**TerraForge Studio - Professional 3D Terrain Generator** 🌍

