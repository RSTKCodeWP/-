# 📖 TerraForge Studio - User Guide

## 🚀 Getting Started

### Installation

#### Windows
1. Download `TerraForge-Studio-vX.X.X-Windows-Portable.zip`
2. Extract to any folder (e.g., `C:\TerraForge Studio`)
3. Run `TerraForge Studio.exe`

**Or use installer:**
1. Download `TerraForge-Studio-Setup-vX.X.X.exe`
2. Run installer
3. Launch from Start Menu

#### Linux
1. Download `TerraForge-Studio-vX.X.X-Linux-x86_64.AppImage`
2. Make executable: `chmod +x TerraForge-Studio-*.AppImage`
3. Run: `./TerraForge-Studio-*.AppImage`

#### macOS
1. Download `TerraForge-Studio-vX.X.X-macOS.dmg`
2. Open DMG and drag to Applications
3. Right-click → Open (first time only)

---

## 🗺️ Creating Your First Terrain

### Step 1: Choose Location

1. Click **"New Project"**
2. Enter location:
   - City name (e.g., "London")
   - Coordinates (e.g., "51.5074, -0.1278")
   - Or click on map

### Step 2: Define Area

1. Click **"Draw Rectangle"** on map
2. Drag to define area
3. Or enter bounds manually

**Recommended sizes:**
- Small: 1-5 km² (good for testing)
- Medium: 5-25 km² (cities)
- Large: 25-100 km² (regions)

### Step 3: Configure Settings

#### Resolution
- **512x512** - Low detail, fast generation
- **1024x1024** - Medium detail (recommended)
- **2048x2048** - High detail
- **4096x4096** - Ultra detail (slow)

#### Elevation Source
- **SRTM** - Free, 30m resolution, global
- **OpenTopography** - High quality, requires API key
- **Sentinel Hub** - Satellite imagery, requires subscription

#### Export Format
- **Unreal Engine 5** - Heightmaps + landscape
- **Unity** - RAW heightmaps + terrain
- **GLTF** - Universal 3D mesh
- **GeoTIFF** - GIS raster data

### Step 4: Generate

1. Click **"Generate Terrain"**
2. Wait for processing (1-10 minutes depending on size)
3. Preview in 3D viewer
4. Download results

---

## 🎨 Features Guide

### 3D Preview

- **Rotate:** Left-click + drag
- **Pan:** Right-click + drag
- **Zoom:** Mouse wheel
- **Reset view:** Press `R`

**Visualization modes:**
- Terrain with texture
- Wireframe
- Elevation colored
- Satellite overlay

### Layer Management

Add additional layers:
- **Roads** - OpenStreetMap roads
- **Buildings** - Building footprints
- **Water** - Rivers, lakes, coastline
- **Vegetation** - Forest coverage

### Advanced Settings

#### Terrain Processing
- **Smooth terrain:** Reduce noise
- **Exaggerate height:** Scale vertical (1.0 = realistic)
- **Apply erosion:** Simulate natural erosion
- **Add detail noise:** Procedural detail

#### Texture Settings
- **Satellite imagery:** Use real satellite photos
- **Procedural textures:** Auto-generate based on slope/elevation
- **Custom textures:** Upload your own

---

## 🎮 Game Engine Integration

### Unreal Engine 5

1. Generate with **UE5 export format**
2. Download ZIP package
3. Extract to your UE5 project folder
4. Run import script: `ImportTerrain.bat`
5. Landscape appears in your level!

**What's included:**
- Heightmap (16-bit PNG)
- Weight maps for texturing
- Spline data for roads/rivers
- Import script (Blueprint)

### Unity

1. Generate with **Unity export format**
2. Download ZIP package
3. Drag `Terrain.asset` into Unity project
4. Run `SetupTerrain.cs` script
5. Terrain ready to use!

**What's included:**
- RAW heightmap
- Splat maps for textures
- Prefabs for objects
- Setup script (C#)

---

## 🔧 Configuration

### Environment Variables

Create `.env` file in app directory:

```ini
# Premium Data Sources (Optional)
SENTINELHUB_CLIENT_ID=your_client_id
SENTINELHUB_CLIENT_SECRET=your_client_secret
OPENTOPOGRAPHY_API_KEY=your_api_key

# AI Features (Optional - requires Ollama)
OLLAMA_HOST=http://localhost:11434
OLLAMA_VISION_MODEL=llava
OLLAMA_CODER_MODEL=codellama

# Application Settings
MAX_AREA_KM2=100
DEFAULT_RESOLUTION=2048
CACHE_ENABLED=true
CACHE_EXPIRY_DAYS=30
```

### API Keys

#### Sentinel Hub (Satellite Imagery)
1. Sign up: https://www.sentinel-hub.com/
2. Create account and get credentials
3. Add to `.env` file

#### OpenTopography (High-res Elevation)
1. Register: https://opentopography.org/
2. Request API key
3. Add to `.env` file

---

## 💾 Managing Projects

### Save/Load Projects

- **Auto-save:** Enabled by default (every 2 minutes)
- **Manual save:** Ctrl+S or File → Save
- **Load project:** File → Open

### Export Results

**Export formats:**
- ZIP (complete package)
- Individual files
- Cloud upload (coming soon)

**Export location:**
- Windows: `Documents\TerraForge\Exports`
- Linux: `~/TerraForge/Exports`
- macOS: `~/Documents/TerraForge/Exports`

---

## 🐛 Troubleshooting

### Common Issues

**Q: Generation fails with "No data available"**
- Area too large (reduce size)
- No elevation data for region
- Internet connection issue

**Q: 3D preview is slow**
- Reduce resolution
- Disable satellite overlay
- Update graphics drivers

**Q: Export file is huge**
- Reduce resolution
- Use compression
- Export as tiles

### Performance Tips

1. **Start small:** Test with 1-5 km² first
2. **Cache data:** Enable caching for faster regeneration
3. **Close other apps:** Free up RAM
4. **Use SSD:** Faster file operations

### Getting Help

- 📖 Documentation: https://github.com/bobberdolle1/TerraForge-Studio/wiki
- 🐛 Report bugs: https://github.com/bobberdolle1/TerraForge-Studio/issues
- 💬 Discussions: https://github.com/bobberdolle1/TerraForge-Studio/discussions

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New project |
| `Ctrl+O` | Open project |
| `Ctrl+S` | Save project |
| `Ctrl+E` | Export |
| `Ctrl+G` | Generate terrain |
| `F5` | Refresh preview |
| `R` | Reset camera |
| `Tab` | Toggle 2D/3D view |

---

## 🎓 Tutorials

### Tutorial 1: Creating a City Terrain

1. Search for "New York City"
2. Select Manhattan area (~10 km²)
3. Resolution: 2048x2048
4. Enable: Roads, Buildings, Water
5. Export to UE5
6. Import in Unreal Engine

### Tutorial 2: Mountain Range

1. Search for "Swiss Alps"
2. Draw rectangle around peaks
3. Resolution: 4096x4096
4. Exaggerate height: 1.5x
5. Apply erosion simulation
6. Export to Unity

### Tutorial 3: Coastal Area

1. Search for "Malibu Beach"
2. Include ocean area
3. Enable water layer
4. Add satellite imagery
5. Export to GLTF
6. View in any 3D software

---

## 📊 Technical Specifications

### Supported Formats

**Input:**
- Location search (geocoding)
- Coordinates (lat/lon)
- Bounding box
- GeoJSON polygon

**Output:**
- PNG (heightmaps)
- RAW (Unity)
- TIFF (GIS)
- GLTF/GLB (3D mesh)
- FBX (3D mesh)

### Data Sources

- **OpenStreetMap:** Vector data (roads, buildings)
- **SRTM:** 30m/90m elevation
- **ASTER GDEM:** 30m elevation
- **Sentinel Hub:** 10m satellite imagery
- **OpenTopography:** 0.5m-30m elevation

---

## 📞 Support

Need help? We're here for you!

- 📧 Email: support@terraforge.studio
- 💬 Discord: [Join our community](#)
- 🐦 Twitter: [@TerraForgeStudio](#)

---

**Happy terrain generating! 🗺️✨**
