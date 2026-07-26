# 🔨 Руководство по сборке / Build Guide

> Полное руководство по сборке TerraForge Studio для Windows, Linux и macOS  
> Complete guide for building TerraForge Studio for Windows, Linux and macOS

---

## 📋 Требования / Prerequisites

### Все платформы / All Platforms

- **Node.js** 18+ ([скачать / download](https://nodejs.org))
- **Rust** 1.70+ ([установить / install](https://rustup.rs))
- **npm** (входит в Node.js / included with Node.js)

### Windows
- **Visual Studio Build Tools** или / or **Visual Studio 2019+**
- **WebView2** (обычно уже установлен / usually pre-installed)

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y \
    libgtk-3-dev \
    libwebkit2gtk-4.0-dev \
    libappindicator3-dev \
    librsvg2-dev \
    patchelf
```

### macOS
```bash
xcode-select --install
```

---

## 🚀 Быстрая сборка / Quick Build

### Windows (PowerShell)
```powershell
# Полная сборка / Full build
.\build.ps1

# Пропустить сборку фронтенда / Skip frontend build
.\build.ps1 -SkipFrontend

# Debug сборка / Debug build
.\build.ps1 -Target debug
```

### Linux/macOS (Bash)
```bash
# Сделать исполняемым / Make executable
chmod +x build.sh

# Полная сборка / Full build
./build.sh

# Пропустить сборку фронтенда / Skip frontend build
./build.sh --skip-frontend

# Debug сборка / Debug build
./build.sh --debug
```

---

## 📦 Ручная сборка / Manual Build

### 1. Подготовка / Preparation

```bash
# Клонировать репозиторий / Clone repository
git clone https://github.com/your-username/terraforge-studio.git
cd terraforge-studio

# Установить зависимости Rust / Install Rust dependencies
cd frontend-new/src-tauri
cargo fetch
cd ../..
```

### 2. Сборка Frontend / Build Frontend

```bash
cd frontend-new

# Установить зависимости / Install dependencies
npm install

# Собрать production build / Build for production
npm run build

cd ..
```

### 3. Сборка Tauri / Build Tauri

```bash
cd frontend-new

# Production сборка / Production build
npm run tauri build

# ИЛИ Debug сборка / OR Debug build
npm run tauri build -- --debug

cd ..
```

---

## 🎯 Выходные файлы / Output Files

### Windows
После сборки файлы будут в / After build, files will be in:
- **MSI installer**: `frontend-new/src-tauri/target/release/bundle/msi/TerraForge Studio_*.msi`
- **NSIS installer**: `frontend-new/src-tauri/target/release/bundle/nsis/TerraForge Studio_*.exe`

### Linux
- **DEB package**: `frontend-new/src-tauri/target/release/bundle/deb/terraforge-studio_*.deb`
- **AppImage**: `frontend-new/src-tauri/target/release/bundle/appimage/terraforge-studio_*.AppImage`

### macOS
- **DMG**: `frontend-new/src-tauri/target/release/bundle/dmg/TerraForge Studio_*.dmg`
- **App Bundle**: `frontend-new/src-tauri/target/release/bundle/macos/TerraForge Studio.app`

---

## 🤖 Автоматическая сборка / Automated Build

### GitHub Actions

При создании тега релиза автоматически запустится сборка для всех платформ:  
When creating a release tag, builds for all platforms will start automatically:

```bash
# Создать тег / Create tag
git tag v1.0.0

# Отправить тег / Push tag
git push origin v1.0.0
```

GitHub Actions автоматически:  
GitHub Actions will automatically:
1. ✅ Соберет для Windows, Linux и macOS / Build for Windows, Linux and macOS
2. ✅ Создаст GitHub Release / Create GitHub Release
3. ✅ Загрузит все артефакты / Upload all artifacts

### Ручной запуск / Manual Trigger

Можно также запустить сборку вручную через GitHub Actions:  
You can also trigger build manually via GitHub Actions:

1. Перейти в / Go to **Actions** → **Build and Release**
2. Нажать / Click **Run workflow**
3. Выбрать ветку / Select branch
4. Нажать / Click **Run workflow**

---

## 🔧 Настройка подписи / Code Signing Setup

### Windows

1. Получить сертификат подписи кода / Obtain code signing certificate
2. Настроить в / Configure in `tauri.conf.json`:

```json
{
  "tauri": {
    "bundle": {
      "windows": {
        "certificateThumbprint": "YOUR_CERT_THUMBPRINT",
        "digestAlgorithm": "sha256",
        "timestampUrl": "http://timestamp.digicert.com"
      }
    }
  }
}
```

### macOS

```bash
# Импорт сертификата / Import certificate
security import cert.p12 -k ~/Library/Keychains/login.keychain

# Настроить в tauri.conf.json / Configure in tauri.conf.json
{
  "tauri": {
    "bundle": {
      "macOS": {
        "signingIdentity": "Developer ID Application: Your Name"
      }
    }
  }
}
```

### Для GitHub Actions / For GitHub Actions

Добавить секреты в репозиторий / Add secrets to repository:
- `TAURI_PRIVATE_KEY` - приватный ключ / private key
- `TAURI_KEY_PASSWORD` - пароль ключа / key password

```bash
# Генерация ключа / Generate key
npm run tauri signer generate -- -w ~/.tauri/myapp.key

# Добавить в GitHub Secrets / Add to GitHub Secrets
cat ~/.tauri/myapp.key
```

---

## 🐛 Решение проблем / Troubleshooting

### Windows

**Ошибка: "WebView2 not found"**
```powershell
# Скачать и установить / Download and install
# https://developer.microsoft.com/en-us/microsoft-edge/webview2/
```

**Ошибка: "MSVC not found"**
```powershell
# Установить Visual Studio Build Tools / Install Visual Studio Build Tools
# https://visualstudio.microsoft.com/downloads/
```

### Linux

**Ошибка: "webkit2gtk not found"**
```bash
sudo apt-get install libwebkit2gtk-4.0-dev
```

**Ошибка: Permission denied**
```bash
chmod +x build.sh
```

### macOS

**Ошибка: "Command Line Tools not found"**
```bash
xcode-select --install
```

**Ошибка сборки для ARM / Build error for ARM**
```bash
# Установить Rosetta 2 / Install Rosetta 2
softwareupdate --install-rosetta
```

---

## 🎨 Кастомизация сборки / Build Customization

### Изменить версию / Change Version

Отредактировать / Edit `frontend-new/src-tauri/tauri.conf.json`:
```json
{
  "package": {
    "productName": "TerraForge Studio",
    "version": "1.0.0"
  }
}
```

### Изменить иконку / Change Icon

Заменить иконки в / Replace icons in:
- `frontend-new/src-tauri/icons/`

Требуемые форматы / Required formats:
- Windows: `.ico`
- macOS: `.icns`
- Linux: `.png` (различные размеры / various sizes)

### Настроить installer / Configure Installer

**Windows (NSIS):**
```json
{
  "tauri": {
    "bundle": {
      "windows": {
        "wix": {
          "language": "en-US"
        }
      }
    }
  }
}
```

**macOS (DMG):**
```json
{
  "tauri": {
    "bundle": {
      "macOS": {
        "minimumSystemVersion": "10.15"
      }
    }
  }
}
```

---

## 📊 Размеры сборок / Build Sizes

Типичные размеры / Typical sizes:

| Платформа / Platform | Размер / Size |
|---------------------|---------------|
| Windows (MSI)       | ~25-35 MB     |
| Windows (NSIS)      | ~25-35 MB     |
| macOS (DMG)         | ~30-40 MB     |
| Linux (DEB)         | ~40-50 MB     |
| Linux (AppImage)    | ~50-60 MB     |

---

## 🔗 Полезные ссылки / Useful Links

- [Tauri Documentation](https://tauri.app/v1/guides/building/)
- [Rust Installation](https://rustup.rs)
- [Node.js Downloads](https://nodejs.org)
- [GitHub Actions Docs](https://docs.github.com/en/actions)

---

## 📝 Чеклист перед релизом / Pre-Release Checklist

- [ ] Обновить версию в `tauri.conf.json` / Update version in `tauri.conf.json`
- [ ] Обновить `CHANGELOG.md` / Update `CHANGELOG.md`
- [ ] Протестировать на всех платформах / Test on all platforms
- [ ] Проверить подписи / Verify signatures
- [ ] Создать тег релиза / Create release tag
- [ ] Проверить GitHub Actions / Check GitHub Actions
- [ ] Проверить артефакты / Verify artifacts
- [ ] Опубликовать релиз / Publish release

---

**Готово к сборке! / Ready to build!** 🚀
