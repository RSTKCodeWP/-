# Contributing to GyroChad

Thanks for your interest in contributing to GyroChad!

## Development Setup

1. Install Rust (1.70+)
2. Install Ollama and pull models: `ollama pull llama3 llava nomic-embed-text`
3. Run Qdrant: `docker run -p 6333:6333 qdrant/qdrant`
4. Install dependencies: `brew install yt-dlp ffmpeg && pip install whisper-ctranslate2`
5. Clone and build: `cargo build --release`

## Code Style

- Run `cargo fmt` before committing
- Run `cargo clippy` and fix warnings
- Write tests for new features
- Keep functions focused and well-documented

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `cargo test`
5. Commit: `git commit -m "Add amazing feature"`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

## Reporting Issues

- Use GitHub Issues
- Include Rust version, OS, and error logs
- Provide minimal reproduction steps

## Feature Requests

Open an issue with:
- Clear description of the feature
- Use case and benefits
- Potential implementation approach

## Code of Conduct

Be respectful, constructive, and collaborative.
