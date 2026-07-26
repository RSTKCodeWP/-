# 🎤 Voice Recognition Setup Guide

## Overview

CoinFlow Bot supports voice message transcription with two options:

1. **Basic Voice Recognition** (recommended for most users)
   - Uses Google Speech Recognition API (free)
   - Works on all platforms and Python versions
   - No model downloads required
   - ~1-2 second latency

2. **Fast Voice Recognition with Whisper** (advanced users)
   - Uses faster-whisper for local transcription
   - 4-5x faster than online API
   - Privacy-first (no data sent to Google)
   - Requires Python 3.11-3.13 (not compatible with 3.14+)
   - Requires model download (~140 MB)

---

## Option 1: Basic Voice Recognition (Recommended)

### Requirements
- Python 3.11+
- ffmpeg (for audio conversion)

### Installation

**Windows:**
```powershell
# Install ffmpeg
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
# Extract and add to PATH

# Install voice dependencies
poetry install -E voice
```

**Linux:**
```bash
# Install ffmpeg
sudo apt-get install ffmpeg

# Install voice dependencies
poetry install -E voice
```

**macOS:**
```bash
# Install ffmpeg
brew install ffmpeg

# Install voice dependencies
poetry install -E voice
```

### Verify Installation

```bash
# Check ffmpeg
ffmpeg -version

# Check Python packages
poetry run python -c "import speech_recognition; print('OK')"
```

---

## Option 2: Fast Voice Recognition (Advanced)

### Requirements
- Python 3.11, 3.12, or 3.13 (NOT 3.14+)
- ffmpeg
- 2 GB RAM for model
- 500 MB disk space

### Check Python Version

```bash
python --version
# Should show 3.11.x, 3.12.x, or 3.13.x
```

**If you have Python 3.14:**
You need to downgrade to Python 3.12 or use Option 1 (Basic Voice Recognition).

### Installation

```bash
# Install with faster-whisper
poetry install -E voice-fast

# Or install all features with fast voice
poetry install -E all-fast
```

### First Run

When you send the first voice message, the Whisper model will download automatically:
```
Downloading faster-whisper base model... (~140 MB)
✅ Faster-Whisper model 'base' loaded successfully
```

Subsequent voice messages will use the cached model.

---

## Docker Setup

The Docker image automatically includes voice recognition with faster-whisper.

**docker-compose.yml already configured with:**
- ffmpeg
- faster-whisper with CPU optimization
- Model auto-download on first use

Just build and run:
```bash
docker-compose build
docker-compose up -d
```

---

## Troubleshooting

### ffmpeg not found

**Error:** `ffmpeg not found in PATH`

**Solution:**
```bash
# Windows (PowerShell as Administrator)
choco install ffmpeg

# Linux
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Verify
ffmpeg -version
```

### Python 3.14 Compatibility Issue

**Error:** `Unable to find installation candidates for ctranslate2`

**Reason:** faster-whisper requires ctranslate2 and onnxruntime, which don't have wheels for Python 3.14 yet.

**Solutions:**

1. **Use Basic Voice Recognition (easiest):**
   ```bash
   poetry install -E voice
   # Uses Google Speech API instead
   ```

2. **Downgrade Python to 3.12:**
   ```bash
   # Install Python 3.12
   # Then recreate virtual environment
   poetry env use python3.12
   poetry install -E voice-fast
   ```

3. **Wait for library updates:**
   Check https://github.com/SYSTRAN/faster-whisper/issues for Python 3.14 support

### Voice messages not transcribing

**Check logs:**
```bash
# Look for voice-related errors
tail -f logs/coinflow.log | grep voice
```

**Common issues:**
1. ffmpeg not installed → Install ffmpeg
2. Network error (Google API) → Check internet connection
3. Audio format issue → Update pydub: `poetry add pydub`

### Slow transcription

**If using Basic Voice Recognition:**
- This is normal (1-2 seconds) as it uses online API
- Consider switching to faster-whisper for local processing

**If using faster-whisper:**
- Check CPU usage: should be optimized with INT8
- Verify model is cached: `ls ~/.cache/huggingface/hub/`
- Check OMP threads: `echo $OMP_NUM_THREADS` (should be 4-8)

---

## Performance Comparison

| Method | Transcription Time | Privacy | Requirements | Python Version |
|--------|-------------------|---------|--------------|----------------|
| **Basic (Google API)** | 1-2 seconds | Cloud-based | Internet | 3.11+ |
| **Faster-Whisper** | 0.5-1 second | Local | Model download | 3.11-3.13 |

---

## Configuration

### Model Size (faster-whisper only)

Edit `coinflow/services/speech_service.py`:

```python
# Available models:
# - tiny (~39 MB, fastest, least accurate)
# - base (~140 MB, recommended)
# - small (~461 MB, more accurate)
# - medium (~1.5 GB, very accurate)
# - large (~2.9 GB, most accurate)

speech_service = SpeechRecognitionService(
    use_whisper=True, 
    model_size="base"  # Change this
)
```

### Fallback Behavior

The bot automatically falls back:
1. Try faster-whisper (if installed)
2. Try standard whisper (if installed)
3. Try Google Speech API (if SpeechRecognition installed)
4. Show error message

---

## Extras Cheat Sheet

```bash
# Basic voice recognition
poetry install -E voice

# Fast voice recognition with Whisper
poetry install -E voice-fast

# All features without faster-whisper
poetry install -E all

# All features with faster-whisper
poetry install -E all-fast

# Just web app
poetry install -E webapp

# Combine multiple
poetry install -E "voice webapp prediction"
```

---

## Testing

Send a voice message to the bot:

1. Open Telegram
2. Go to your bot
3. Press and hold microphone button
4. Say: "Convert 100 dollars to euros"
5. Release and send

**Expected behavior:**
```
🎤 Обработка голосового сообщения...
🎤 Распознано: Convert 100 dollars to euros
⏳ Генерирую ответ AI...
💱 100 USD = 92.50 EUR
```

---

## Support

**Issues:**
- GitHub: https://github.com/bobberdolle1/CoinFlow/issues
- Check logs: `tail -f logs/coinflow.log`

**Related Documentation:**
- [Quick Start Guide](QUICK_START.md)
- [Docker Guide](DOCKER_GUIDE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
