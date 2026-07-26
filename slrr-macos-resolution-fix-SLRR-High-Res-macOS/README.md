# SLRR macOS Resolution Fix

High resolution support for Street Legal Racing: Redline on macOS (CrossOver/Wine).

## 🎯 Problem

SLRR crashes on macOS when trying to run at resolutions higher than 800x600 due to DXVK/Wine limitations with fullscreen mode.

## ✅ Solution

This tool automatically:
- Switches game to windowed mode
- Sets your chosen resolution
- Creates backups before changes
- Allows easy rollback if something goes wrong

## 📦 Installation

1. Download `resolution_manager.py`
2. Place it in your SLRR game directory
3. Run the game once to create save files
4. Exit the game
5. Run the tool:
```bash
python3 resolution_manager.py
```

## 🎮 Supported Resolutions

### ✅ Stable (Recommended):
- 800x600 (default)
- 1024x768
- **1280x800** (best for most Macs)

### ⚠️ Experimental (May Crash):
- 1440x900
- 1680x1050
- 1920x1080
- 2560x1440
- 2560x1600

## 🚀 Usage

```bash
python3 resolution_manager.py
```

Select a resolution from the menu. The tool will automatically create a backup.

### If Game Crashes:

```bash
python3 resolution_manager.py
# Select "Restore backup"
```

## 🔧 Technical Details

The tool modifies `save/game/options` file:
- Offset 0x10: Windowed mode flag (0=fullscreen, 1=windowed)
- Offset 0x14: Width (4 bytes, little-endian)
- Offset 0x18: Height (4 bytes, little-endian)

## ❓ Why Not Fullscreen?

DXVK on macOS cannot switch display to fullscreen exclusive mode for high resolutions. Windowed mode bypasses this limitation.

## 💻 Compatibility

- ✅ macOS (Apple Silicon M1/M2/M3 and Intel)
- ✅ CrossOver 23+
- ✅ Wine 8.0+
- ✅ All SLRR versions (2.3.1 LE, Steam version)

## 🐛 Known Issues

1. **Resolutions above 1280x800 are unstable** - game may crash
2. **Not all resolutions supported** - game validates resolutions
3. **Windowed mode required** - fullscreen doesn't work at high resolutions

## ⚠️ Disclaimer

Use at your own risk. Always backup your saves before experimenting.

## 📝 License

MIT License - free to use and modify

## 🤝 Contributing

Pull requests welcome! Please test thoroughly before submitting.

## 🙏 Credits

Created for the SLRR macOS community.

Special thanks to the SLRR modding community and XOF's Essential Collection.
