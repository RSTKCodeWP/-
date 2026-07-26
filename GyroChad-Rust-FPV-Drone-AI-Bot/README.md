# GyroChad 🚁

[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange.svg)](https://www.rust-lang.org/)
[![Tokio](https://img.shields.io/badge/tokio-async-blue.svg)](https://tokio.rs/)
[![Ollama](https://img.shields.io/badge/ollama-AI-green.svg)](https://ollama.ai/)
[![Qdrant](https://img.shields.io/badge/qdrant-vector%20DB-red.svg)](https://qdrant.tech/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**AI-Powered FPV Drone Assistant** — Telegram bot with RAG pipeline, computer vision, and blackbox log analysis for FPV pilots.

## 🔥 Features

- **RAG Pipeline**: Retrieval-Augmented Generation using Qdrant vector database
- **Computer Vision**: Analyze Betaflight/Blackbox screenshots with llava vision model
- **Blackbox Analysis**: Parse and analyze .bbl flight logs with automated recommendations
- **Voice Support**: Transcribe voice messages using Whisper
- **Conversational Memory**: Context-aware dialogue with short-term memory (10 messages)
- **Knowledge Injection**: CLI tool to download YouTube videos, transcribe, and inject into vector DB

## 🏗️ Architecture

```
GyroChad/
├── src/
│   ├── clients/
│   │   ├── ollama_client.rs      # LLM & Vision API
│   │   ├── qdrant_client.rs      # Vector DB operations
│   │   └── rag_engine.rs         # RAG orchestration
│   ├── handlers/
│   │   └── telegram_handler.rs   # Message routing
│   ├── utils/
│   │   ├── audio_processor.rs    # Whisper transcription
│   │   ├── blackbox_parser.rs    # BBL log analysis
│   │   └── media_downloader.rs   # File handling
│   ├── memory.rs                 # Conversation history
│   └── config.rs                 # Environment config
└── knowledge_injector/           # CLI for knowledge base
    ├── youtube_parser.rs         # yt-dlp wrapper
    ├── batch_whisper.rs          # Mass transcription
    ├── text_chunker.rs           # Smart chunking
    └── qdrant_loader.rs          # Vector upload
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull llama3
ollama pull llava
ollama pull nomic-embed-text

# Install Qdrant (Docker)
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage:z \
    qdrant/qdrant

# Install dependencies
brew install yt-dlp ffmpeg
pip install whisper-ctranslate2

# Install blackbox_decode (optional, for log analysis)
# Download from: https://github.com/betaflight/blackbox-tools
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your credentials
```

```env
TELOXIDE_TOKEN=your_telegram_bot_token
BOT_USERNAME=your_bot_username

OLLAMA_URL=http://localhost:11434
QDRANT_URL=http://localhost:6333

EMBEDDING_MODEL=nomic-embed-text
LLM_MODEL=llama3
VISION_MODEL=llava

MAX_HISTORY_MESSAGES=10
```

### Build & Run

```bash
# Build release binary
cargo build --release

# Run bot
./target/release/gyro_chad

# Or with cargo
cargo run --release
```

## 📚 Knowledge Injection

Populate the vector database with FPV knowledge:

```bash
# Full pipeline: download → transcribe → inject
./target/release/knowledge_injector full \
  --url "https://youtube.com/watch?v=VIDEO_ID" \
  --ollama-url "http://localhost:11434" \
  --qdrant-url "http://localhost:6333"

# Or step-by-step
./target/release/knowledge_injector download --url "URL" --output-dir raw_audio
./target/release/knowledge_injector transcribe --input-dir raw_audio --output-dir raw_texts
./target/release/knowledge_injector inject --input-dir raw_texts
```

## 💬 Usage

### Text Queries
```
User: Какие моторы лучше для 5" фристайла?
Bot: [RAG-enhanced response with context from knowledge base]
```

### Vision Analysis
```
User: [sends Betaflight screenshot]
Bot: 📷 Вижу настройки PID: P=45, I=80, D=35. Рекомендую...
```

### Blackbox Analysis
```
User: [uploads .bbl file]
Bot: 📊 BLACKBOX LOG ANALYSIS
     D-TERM NOISE: Roll 23.4, Pitch 28.1
     MAX GYRO PEAKS: Roll 856°/s, Pitch 912°/s
     RECOMMENDATIONS: ✅ Log looks clean
```

### Voice Messages
```
User: [voice message]
Bot: [transcribes and responds with RAG context]
```

## 🛠️ Development

```bash
# Check code
cargo check

# Run tests
cargo test

# Format code
cargo fmt

# Lint
cargo clippy
```

## 📦 Tech Stack

- **Language**: Rust 1.70+
- **Async Runtime**: Tokio
- **Telegram**: teloxide
- **LLM**: Ollama (llama3, llava)
- **Vector DB**: Qdrant
- **Embeddings**: nomic-embed-text
- **Transcription**: whisper-ctranslate2
- **Memory**: moka (in-memory cache)

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- Betaflight community for blackbox tools
- Ollama team for local LLM inference
- Qdrant for vector search
- OpenAI Whisper for transcription

---

**Built with 🔥 by FPV pilots, for FPV pilots**
