# GyroChad 🚁

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [bobberdolle1/GyroChad](https://github.com/bobberdolle1/GyroChad) |
| Локальна тека | `GyroChad-Rust-FPV-Drone-AI-Bot` |
| У бібліотеці | keep |
| Категорії каталогу | `fc`, `ai` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-03-21 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**AI-Powered FPV Drone Assistant** — Telegram bot with RAG pipeline, computer vision, and blackbox log analysis for FPV pilots.

_З README.md, без переказу._

## Для чого

🚁 AI-Powered FPV Drone Assistant - Telegram bot with RAG, Vision, and Blackbox Analysis

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «betaflight».


Теми GitHub: `ai`, `assistant`, `betaflight`, `blackbox`, `drone`, `fpv`, `rag`, `rust`, `telegram-bot`.

## Функція

Список із розділу features / можливості в README:

- **RAG Pipeline**: Retrieval-Augmented Generation using Qdrant vector database
- **Computer Vision**: Analyze Betaflight/Blackbox screenshots with llava vision model
- **Blackbox Analysis**: Parse and analyze .bbl flight logs with automated recommendations
- **Voice Support**: Transcribe voice messages using Whisper
- **Conversational Memory**: Context-aware dialogue with short-term memory (10 messages)
- **Knowledge Injection**: CLI tool to download YouTube videos, transcribe, and inject into vector DB

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CONTRIBUTING.md`
- `DEPLOY.sh`
- `gyro_chad/`
- `LICENSE`
- `README.md`

Типи файлів за вибіркою (27 файлів, глибина до 3): Rust (19), (без суфікса) (3), Markdown (2), .example (1), shell (1), TOML (1).

Фрагмент README про будову:

### 🏗️ Architecture

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

## Що треба

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


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Build & Run

```bash
# Build release binary
cargo build --release

# Run bot
./target/release/gyro_chad

# Or with cargo
cargo run --release
```

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../GyroChad-Rust-FPV-Drone-AI-Bot/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `GyroChad-Rust-FPV-Drone-AI-Bot/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/bobberdolle1__GyroChad.md`.
