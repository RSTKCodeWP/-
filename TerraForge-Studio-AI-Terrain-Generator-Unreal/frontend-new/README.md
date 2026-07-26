# TerraForge Studio - Frontend

Modern React + TypeScript frontend for TerraForge Studio.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## 📦 Features

- ✅ **React 18** + TypeScript
- ✅ **Vite** - Fast build tool
- ✅ **Tailwind CSS** - Utility-first styling
- ✅ **Leaflet** - Interactive 2D map with drawing tools
- ✅ **CesiumJS** - 3D terrain preview (placeholder ready)
- ✅ **Axios** - API integration
- ✅ **Lucide Icons** - Modern icon set

## 🏗️ Project Structure

```
src/
├── components/         # React components
│   ├── MapSelector.tsx       # 2D map with area selection
│   ├── ExportPanel.tsx       # Export configuration
│   ├── StatusMonitor.tsx     # Generation status
│   └── Preview3D.tsx         # 3D preview (CesiumJS)
├── services/
│   └── api.ts               # API client
├── types/
│   └── index.ts             # TypeScript types
├── styles/
│   └── index.css            # Global styles
├── App.tsx                  # Main application
└── main.tsx                 # Entry point
```

## 🔌 API Integration

The frontend connects to the FastAPI backend running on `http://localhost:8000`.

API endpoints used:
- `GET /api/health` - Check API health
- `GET /api/sources` - Get available data sources
- `GET /api/formats` - Get export format info
- `POST /api/generate` - Start terrain generation
- `GET /api/status/{task_id}` - Check generation status

## 🎨 UI Components

### MapSelector
- Interactive Leaflet map
- Drawing tools (rectangle, polygon)
- Real-time area calculation
- OpenStreetMap tiles

### ExportPanel
- Terrain name input
- Resolution selection (UE5/Unity optimized)
- Export format selection (multiple)
- Elevation source selection
- Feature toggles (roads, buildings, weightmaps)

### StatusMonitor
- Real-time progress tracking
- Status indicators
- Error display
- Download links for completed exports

### Preview3D
- 3D terrain visualization placeholder
- Ready for full CesiumJS integration

## 🔧 Configuration

### Environment Variables

Create `.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

### Tailwind Customization

Edit `tailwind.config.js` to customize colors, spacing, etc.

## 📱 Responsive Design

- Desktop-first design
- Responsive grid layout
- Mobile-friendly controls
- Glass morphism UI effects

## 🚧 Future Enhancements

- [ ] Full CesiumJS 3D preview integration
- [ ] Real-time terrain streaming
- [ ] Drag-and-drop area upload
- [ ] Export preset management
- [ ] Generation history
- [ ] User authentication
- [ ] Dark mode toggle
- [ ] Internationalization (i18n)

## 📄 License

MIT License - See parent project LICENSE file

