"""
TerraForge Studio - Frontend Tests
Basic Playwright tests for UI validation
"""

import pytest
from playwright.sync_api import Page, expect


def test_homepage_loads(page: Page):
    """Test that homepage loads successfully"""
    page.goto("http://localhost:3000")

    # Check title
    expect(page).to_have_title("TerraForge Studio - Professional 3D Terrain Generator")

    # Check main heading
    heading = page.locator("h1")
    expect(heading).to_contain_text("TerraForge Studio")


def test_map_is_visible(page: Page):
    """Test that the map component is visible"""
    page.goto("http://localhost:3000")

    # Map should be visible
    map_container = page.locator("#map")
    expect(map_container).to_be_visible()


def test_export_panel_exists(page: Page):
    """Test that export configuration panel exists"""
    page.goto("http://localhost:3000")

    # Export panel elements
    expect(page.locator("text=Export Configuration")).to_be_visible()
    expect(page.locator("text=Terrain Name")).to_be_visible()
    expect(page.locator("text=Generate Terrain")).to_be_visible()


def test_3d_preview_tab(page: Page):
    """Test that 3D preview tab can be clicked"""
    page.goto("http://localhost:3000")

    # Click 3D Preview tab
    preview_tab = page.locator("text=3D Preview")
    preview_tab.click()

    # Check that 3D preview is now visible
    expect(page.locator("text=3D Preview").first).to_be_visible()


def test_export_format_selection(page: Page):
    """Test export format checkboxes"""
    page.goto("http://localhost:3000")

    # Check that format checkboxes exist
    unreal_checkbox = page.locator("input[type='checkbox']").first
    expect(unreal_checkbox).to_be_visible()

    # Should be checked by default (unreal5)
    expect(unreal_checkbox).to_be_checked()


def test_resolution_dropdown(page: Page):
    """Test resolution selection dropdown"""
    page.goto("http://localhost:3000")

    # Resolution dropdown
    resolution_select = page.locator("select").first
    expect(resolution_select).to_be_visible()

    # Change resolution
    resolution_select.select_option("4096")
    expect(resolution_select).to_have_value("4096")


def test_terrain_name_input(page: Page):
    """Test terrain name can be entered"""
    page.goto("http://localhost:3000")

    # Find terrain name input
    name_input = page.locator("input[type='text']").first

    # Type a name
    name_input.fill("test_terrain_001")
    expect(name_input).to_have_value("test_terrain_001")


def test_generate_button_disabled_without_area(page: Page):
    """Test that generate button is disabled without selected area"""
    page.goto("http://localhost:3000")

    # Generate button should be disabled initially
    generate_btn = page.locator("text=Generate Terrain")
    expect(generate_btn).to_be_disabled()


@pytest.mark.skip(reason="Requires backend API running")
def test_api_health_check(page: Page):
    """Test that frontend can connect to backend API"""
    page.goto("http://localhost:3000")

    # Wait for health check to complete
    page.wait_for_timeout(2000)

    # Should show available sources count
    expect(page.locator("text=sources available")).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

