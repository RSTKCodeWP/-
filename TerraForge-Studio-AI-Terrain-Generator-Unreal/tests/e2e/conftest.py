"""
Pytest configuration for TerraForge Studio tests
"""

import pytest
from playwright.sync_api import Browser, Page, Playwright


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Browser:
    """Launch browser for testing"""
    return playwright.chromium.launch(headless=True)


@pytest.fixture
def page(browser: Browser) -> Page:
    """Create a new page for each test"""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()

