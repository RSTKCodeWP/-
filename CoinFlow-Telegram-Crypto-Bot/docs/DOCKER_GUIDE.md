# 🐳 CoinFlow Bot - Docker Deployment Guide

Complete guide for deploying CoinFlow Bot v3.1 with Qwen3-8B and faster-whisper using Docker.

---

## 📋 Prerequisites

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **16 GB RAM** minimum (32 GB recommended for AI + voice recognition)
- **25 GB** free disk space (includes Whisper models)
- **ffmpeg** (included in Docker image for voice processing)

### Install Docker

**Windows:**
- Download Docker Desktop: https://www.docker.com/products/docker-desktop

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER
```

**macOS:**
- Download Docker Desktop: https://www.docker.com/products/docker-desktop

---

## 🚀 Quick Start (Automated)

### Linux/macOS:
```bash
# Make script executable
chmod +x docker-init.sh

# Run setup
./docker-init.sh
```

### Windows (PowerShell):
```powershell
# Use docker-run.bat or manual steps below
.\docker-run.bat
```

---

## 📝 Manual Setup

### 1. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env and set your bot token
nano .env  # or use any text editor
```

**Required settings in `.env`:**
```bash
TELEGRAM_BOT_TOKEN=your_token_here
ADMIN_IDS=your_telegram_id
```

### 2. Create Directories

```bash
mkdir -p data logs
```

### 3. Build and Start

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d
```

### 4. Download Qwen3-8B Model

```bash
# Wait for Ollama to be ready (20-30 seconds)
sleep 30

# Pull the model (5-10 minutes)
docker exec coinflow-ollama ollama pull qwen3:8b
```

### 5. Verify

```bash
# Check logs
docker-compose logs -f coinflow-bot

# Should see:
# ✅ Model qwen3:8b is available
# ✅ AI service (Qwen3-8B) is ready!
# ✅ Faster-Whisper model loaded successfully
# 🤖 CoinFlow Bot v3.1 is running...
```

---

## 📊 Service Management

### View Logs
```bash
# All services
docker-compose logs -f

# Only bot
docker-compose logs -f coinflow-bot

# Only Ollama
docker-compose logs -f ollama
```

### Stop Services
```bash
docker-compose stop
```

### Restart Services
```bash
docker-compose restart
```

### Stop and Remove
```bash
docker-compose down

# Remove volumes too (deletes data)
docker-compose down -v
```

### Update
```bash
# Pull latest code
git pull

# Rebuild
docker-compose build

# Restart
docker-compose up -d
```

---

## 🔧 Architecture

```
┌─────────────────────────────────────┐
│     Docker Compose Stack            │
├─────────────────────────────────────┤
│                                     │
│  ┌──────────────────────────────┐  │
│  │  CoinFlow Bot Container      │  │
│  │  - Python 3.12               │  │
│  │  - Telegram Bot              │  │
│  │  - AI Service (Qwen3-8B)     │  │
│  │  - faster-whisper (voice)    │  │
│  │  - ffmpeg (audio processing) │  │
│  │  - All Features              │  │
│  └──────────────────────────────┘  │
│               │                     │
│               │ Connects to         │
│               ▼                     │
│      Ollama (host machine)          │
│      - Port: 11434                  │
│                                     │
└─────────────────────────────────────┘
         │
         ▼
   Host Volumes:
   - ./data (database)
   - ./logs (logs)
```

### Key Components:

1. **CoinFlow Bot Container:**
   - Main application container
   - Includes all Python dependencies
   - ffmpeg for voice message processing
   - faster-whisper for speech recognition (4-5x faster than openai-whisper)
   - Optimized with INT8 quantization for CPU

2. **Ollama Service:**
   - Runs on host machine (not in container)
   - Accessible via `http://host.docker.internal:11434`
   - Provides AI capabilities (Qwen3-8B)

3. **Voice Recognition:**
   - faster-whisper with base model (~140 MB)
   - Automatic model download on first run
   - CPU-optimized with multi-threading

---

## 🐛 Troubleshooting

### Ollama not starting

**Check logs:**
```bash
docker-compose logs ollama
```

**Restart Ollama:**
```bash
docker-compose restart ollama
```

### Model not downloading

**Check Ollama is running:**
```bash
docker exec coinflow-ollama ollama list
```

**Manually pull:**
```bash
docker exec coinflow-ollama ollama pull qwen3:8b
```

### Bot can't connect to Ollama

**Check network:**
```bash
docker exec coinflow-bot ping ollama
```

**Check Ollama URL in logs:**
```bash
docker-compose logs coinflow-bot | grep OLLAMA
```

### Out of memory

**Check Docker resources:**
```bash
docker stats
```

**Increase Docker memory:**
- Docker Desktop → Settings → Resources → Memory
- Set to at least 16 GB

**Or use smaller model:**
```bash
# In .env
OLLAMA_MODEL=qwen3:3b
```

### Permission errors

```bash
# Fix data directory permissions
sudo chown -R $USER:$USER data logs

# Or run with sudo
sudo docker-compose up -d
```

---

## 🎮 GPU Support (Optional)

For faster AI responses with NVIDIA GPU:

### 1. Install NVIDIA Container Toolkit

**Linux:**
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Update docker-compose.yml

Add to `ollama` service:
```yaml
ollama:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### 3. Restart

```bash
docker-compose down
docker-compose up -d
```

### 4. Verify GPU

```bash
docker exec coinflow-ollama nvidia-smi
```

---

## 📈 Performance

### AI Response Times

| Configuration | Response Time |
|--------------|---------------|
| CPU only (4 cores, 16GB RAM) | 15-30 sec |
| CPU (8 cores, 32GB RAM) | 5-15 sec |
| GPU (NVIDIA 8GB VRAM) | 2-5 sec |

### Voice Recognition Performance (v3.1)

| Metric | openai-whisper | faster-whisper | Improvement |
|--------|----------------|----------------|-------------|
| **Transcription Time** (10s audio) | 3-4 seconds | 0.8-1 second | **4x faster** ⚡ |
| **Memory Usage** | 1.2 GB | 600 MB | **50% less** 💾 |
| **Model Size** (base) | 290 MB | 140 MB | **52% smaller** |

### Optimization Settings

The Docker image includes:
- `OMP_NUM_THREADS=4` - OpenMP multi-threading
- `MKL_NUM_THREADS=4` - Math Kernel Library optimization
- INT8 quantization for faster-whisper
- Multi-stage build for smaller image size

---

## 🔒 Security

**Firewall:**
```bash
# Only expose Telegram bot port if needed
# Ollama port (11434) is NOT exposed to internet by default
```

**Environment variables:**
```bash
# Never commit .env to Git
# .env is already in .gitignore
```

**Updates:**
```bash
# Regularly update base images
docker-compose pull
docker-compose up -d
```

---

## 📦 Backup

### Backup Data
```bash
# Backup database and logs
tar -czf coinflow-backup-$(date +%Y%m%d).tar.gz data logs .env

# Backup Ollama models (optional, can be re-downloaded)
docker run --rm -v coinflow_ollama-data:/data -v $(pwd):/backup alpine tar -czf /backup/ollama-models.tar.gz -C /data .
```

### Restore
```bash
# Restore data
tar -xzf coinflow-backup-YYYYMMDD.tar.gz

# Restart services
docker-compose restart
```

---

## 🆘 Support

**Logs location:**
- Bot logs: `./logs/coinflow.log`
- Docker logs: `docker-compose logs`

**Common commands:**
```bash
# Check container status
docker-compose ps

# Check resource usage
docker stats

# Enter container shell
docker exec -it coinflow-bot bash

# Check Ollama models
docker exec coinflow-ollama ollama list

# Test Ollama API
docker exec coinflow-bot curl http://ollama:11434/api/tags
```

---

## ✅ Production Checklist

- [ ] Docker and Docker Compose installed
- [ ] `.env` configured with bot token
- [ ] Firewall configured (block 11434 from internet)
- [ ] 16+ GB RAM available
- [ ] 20+ GB disk space
- [ ] Qwen3-8B model downloaded
- [ ] Bot starts without errors
- [ ] Telegram commands work
- [ ] AI responses work
- [ ] Voice messages work (if enabled)
- [ ] Backups configured

---

**Version:** 3.1.0  
**Last updated:** 2025-10-21  
**Author:** bobberdolle1

---

## 🎤 Voice Recognition Setup

### Automatic Setup (Included in Docker)

The Docker image automatically includes:
- ✅ ffmpeg (audio conversion)
- ✅ faster-whisper (speech recognition)
- ✅ SpeechRecognition (fallback)
- ✅ pydub (audio processing)

### First Voice Message

When you send the first voice message:
1. Whisper model downloads automatically (~140 MB for base model)
2. Subsequent messages use cached model
3. Transcription happens in <1 second

### Troubleshooting Voice

**Voice messages not working:**
```bash
# Check ffmpeg is installed
docker exec coinflow-bot which ffmpeg

# Check Python dependencies
docker exec coinflow-bot python -c "import faster_whisper; print('OK')"

# View voice processing logs
docker-compose logs -f coinflow-bot | grep voice
```

**Slow transcription:**
- Check CPU usage: `docker stats coinflow-bot`
- Increase CPU allocation in Docker Desktop settings
- Verify OMP_NUM_THREADS is set: `docker exec coinflow-bot env | grep OMP`

**Model download issues:**
```bash
# Check model cache
docker exec coinflow-bot ls -lh ~/.cache/huggingface/hub/

# Manually download if needed (inside container)
docker exec -it coinflow-bot bash
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```
