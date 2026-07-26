import { describe, it, expect, beforeEach } from 'vitest';
import { useRubyOsdStore } from './ruby-osd-store';
import { isElementEnabled, getFontSize, getTransparency } from '../utils/osd/ruby-osd';

describe('ruby-osd-store', () => {
  beforeEach(() => {
    useRubyOsdStore.getState().reset();
  });

  it('defaults to a populated (Default preset) layout, not an empty one', () => {
    const { params } = useRubyOsdStore.getState();
    expect(isElementEnabled(params, 0, 'battery')).toBe(true);
    expect(isElementEnabled(params, 0, 'altitude')).toBe(true);
    expect(params.screens[0]!.layoutPreset).toBe(3); // Default
  });

  it('toggles an element only on the screen being edited (and marks it Custom)', () => {
    const s = useRubyOsdStore.getState();
    s.setEditingScreen(2);
    s.toggleElement('wind'); // not part of any preset -> starts off
    const { params } = useRubyOsdStore.getState();
    expect(isElementEnabled(params, 2, 'wind')).toBe(true);
    expect(isElementEnabled(params, 0, 'wind')).toBe(false);
    expect(params.screens[2]!.layoutPreset).toBe(4); // Custom
    useRubyOsdStore.getState().toggleElement('wind');
    expect(isElementEnabled(useRubyOsdStore.getState().params, 2, 'wind')).toBe(false);
  });

  it('selecting a preset applies its element set to the edited screen', () => {
    useRubyOsdStore.getState().setEditingScreen(1);
    useRubyOsdStore.getState().setPreset(1); // Minimal
    const { params } = useRubyOsdStore.getState();
    expect(params.screens[1]!.layoutPreset).toBe(1);
    expect(isElementEnabled(params, 1, 'battery')).toBe(true); // Minimal includes battery
    expect(isElementEnabled(params, 1, 'altitude')).toBe(false); // but not altitude
  });

  it('packs font size and transparency into the edited screen preferences', () => {
    useRubyOsdStore.getState().setEditingScreen(0);
    useRubyOsdStore.getState().setFontSize(4);
    useRubyOsdStore.getState().setTransparency(3);
    const prefs = useRubyOsdStore.getState().params.screens[0]!.preferences;
    expect(getFontSize(prefs)).toBe(4);
    expect(getTransparency(prefs)).toBe(3);
  });

  it('setCurrentScreen selects the active screen and clamps to range', () => {
    useRubyOsdStore.getState().setCurrentScreen(3);
    expect(useRubyOsdStore.getState().params.currentScreen).toBe(3);
    useRubyOsdStore.getState().setCurrentScreen(99);
    expect(useRubyOsdStore.getState().params.currentScreen).toBe(4); // 5 screens, clamped
  });
});
