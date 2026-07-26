# Contributing to RealWorldMapGen-BNG

Thank you for your interest in contributing to RealWorldMapGen-BNG! This document provides guidelines and instructions for contributing.

## 🤝 How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Python version, Poetry version)
- Relevant logs or error messages

### Suggesting Features

Feature suggestions are welcome! Please open an issue with:
- Clear description of the feature
- Use case and motivation
- Potential implementation approach (optional)

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
4. **Test your changes**:
   ```bash
   poetry run pytest
   poetry run black realworldmapgen/
   poetry run ruff check realworldmapgen/
   ```
5. **Commit with clear messages**:
   ```bash
   git commit -m "Add: Brief description of changes"
   ```
6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Open a Pull Request**

## 📝 Code Style

- Follow PEP 8 style guide
- Use type hints where appropriate
- Write docstrings for functions and classes
- Keep functions focused and small
- Add comments for complex logic

### Code Formatting

We use:
- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **MyPy** for type checking

Run before committing:
```bash
poetry run black realworldmapgen/
poetry run ruff check realworldmapgen/ --fix
poetry run mypy realworldmapgen/
```

## 🧪 Testing

- Write tests for new features
- Ensure existing tests pass
- Aim for good test coverage

Run tests:
```bash
poetry run pytest
poetry run pytest --cov=realworldmapgen
```

## 📚 Documentation

- Update README.md for user-facing changes
- Add docstrings to new functions/classes
- Update API documentation if endpoints change
- Add examples for new features

## 🏗️ Development Setup

1. **Clone and install**:
   ```bash
   git clone <your-fork-url>
   cd RealWorldMapGen-BNG
   poetry install
   ```

2. **Set up pre-commit hooks** (optional):
   ```bash
   poetry run pre-commit install
   ```

3. **Run in development mode**:
   ```bash
   poetry run uvicorn realworldmapgen.api.main:app --reload
   ```

## 🔍 Code Review Process

All submissions require review. We look for:
- Code quality and style
- Test coverage
- Documentation
- Performance implications
- Security considerations

## 📋 Commit Message Guidelines

Use clear, descriptive commit messages:

- `Add: New feature or functionality`
- `Fix: Bug fix`
- `Update: Improvements to existing features`
- `Refactor: Code restructuring`
- `Docs: Documentation changes`
- `Test: Test additions or changes`
- `Style: Code style changes`

Example:
```
Add: Support for custom road materials in BeamNG exporter

- Add material_map configuration option
- Update BeamNG exporter to use custom materials
- Add tests for material mapping
```

## 🎯 Priority Areas

Current areas where contributions are especially welcome:

1. **Satellite imagery integration**: Implement actual satellite image download and analysis
2. **Performance optimization**: Improve processing speed for large areas
3. **Additional exporters**: Support for other game engines (Unreal, Unity)
4. **Testing**: Expand test coverage
5. **Documentation**: Improve guides and examples
6. **UI/UX**: Enhance web interface

## 🐛 Debugging Tips

- Check backend terminal output for errors
- Enable verbose logging in `.env`: `LOG_LEVEL=DEBUG`
- Use FastAPI docs: `http://localhost:8000/docs`
- Test Ollama separately: `curl http://localhost:11434/api/tags`

## ❓ Questions?

- Open a discussion on GitHub
- Check existing issues and PRs
- Read the documentation

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to RealWorldMapGen-BNG! 🎉
