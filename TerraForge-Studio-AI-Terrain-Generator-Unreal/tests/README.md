# TerraForge Studio - Tests

## 🧪 Test Suite

### Frontend Tests (`test_frontend.py`)
Tests for React UI using Playwright:
- Homepage loading
- Map component visibility
- Export panel functionality
- 3D preview tab switching
- Form inputs and validation

### API Tests (`test_api_integration.py`)
Tests for FastAPI backend:
- API health check
- Data sources endpoint
- Export formats endpoint
- Terrain generation endpoint
- Input validation

## 🚀 Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-asyncio playwright httpx

# Install Playwright browsers
playwright install chromium
```

### Run All Tests

```bash
# From project root
pytest tests/ -v
```

### Run Specific Test Files

```bash
# Frontend tests only (requires frontend running on :3000)
pytest tests/test_frontend.py -v

# API tests only (requires backend running on :8000)
pytest tests/test_api_integration.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=realworldmapgen --cov-report=html
```

## 📋 Test Checklist

Before running tests, ensure:

### For Frontend Tests:
- [ ] Frontend development server is running (`cd frontend-new && npm run dev`)
- [ ] Accessible at `http://localhost:3000`

### For API Tests:
- [ ] Backend API server is running (`poetry run uvicorn realworldmapgen.api.main:app`)
- [ ] Accessible at `http://localhost:8000`
- [ ] `.env` file configured with data source API keys (optional)

## ✅ Expected Results

### Frontend Tests:
- ✅ All UI components render correctly
- ✅ User interactions work (clicks, form inputs)
- ✅ Navigation between tabs functions
- ✅ Generate button properly disabled/enabled

### API Tests:
- ✅ All endpoints return expected status codes
- ✅ Response data matches schema
- ✅ Validation errors caught correctly
- ✅ Terrain generation initiates successfully

## 🐛 Troubleshooting

### Frontend tests fail with "page not found":
```bash
# Ensure frontend is running
cd frontend-new
npm run dev
```

### API tests fail with connection error:
```bash
# Ensure backend is running
poetry run uvicorn realworldmapgen.api.main:app --reload
```

### Playwright browser not found:
```bash
playwright install chromium
```

## 📊 Test Coverage Goals

- Frontend: >80% component coverage
- API: >90% endpoint coverage
- Core modules: >85% code coverage

## 🔄 CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - uses: actions/setup-node@v3
      
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
          cd frontend-new && npm install
      
      - name: Run backend tests
        run: poetry run pytest tests/test_api_integration.py
      
      - name: Run frontend tests
        run: |
          npm run build --prefix frontend-new
          pytest tests/test_frontend.py
```

## 📝 Adding New Tests

1. Create test file in `tests/` directory
2. Follow naming convention: `test_*.py`
3. Use descriptive test function names: `test_feature_behavior()`
4. Add docstrings explaining what is being tested
5. Update this README with new test categories

## 🎯 Manual Testing Scenarios

### Complete Workflow Test:
1. Start backend and frontend
2. Open browser to `http://localhost:3000`
3. Select area on map (draw rectangle)
4. Configure export (name, format, resolution)
5. Click "Generate Terrain"
6. Monitor progress in status panel
7. Download exported files when complete
8. Verify downloaded files exist and are valid

### Multi-Format Export Test:
1. Select multiple export formats (UE5 + Unity + GLTF)
2. Generate terrain
3. Verify all format-specific files are created
4. Check metadata JSON for each format

