import { describe, it, expect, vi, beforeEach } from 'vitest';

function makeStorage(): Storage {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, v);
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    clear: () => store.clear(),
    get length() {
      return store.size;
    },
    key: (i: number) => [...store.keys()][i] ?? null,
  };
}

describe('branding', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('localStorage', makeStorage());
    vi.stubGlobal('document', {
      getElementById: () => null,
      documentElement: { style: { setProperty: vi.fn() } },
    });
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost' } });
  });

  it('getBrand returns default config', async () => {
    const { getBrand, loadBranding } = await import('./branding');
    loadBranding();
    const brand = getBrand();
    expect(brand.appName).toBe('Argus');
    expect(brand.subtitle).toBe('Ground Control Station');
  });

  it('loads from localStorage override', async () => {
    localStorage.setItem('argus_branding', JSON.stringify({ appName: 'TestGCS' }));
    const { getBrand, loadBranding } = await import('./branding');
    loadBranding();
    expect(getBrand().appName).toBe('TestGCS');
  });

  it('applies primaryColor to CSS', async () => {
    localStorage.setItem('argus_branding', JSON.stringify({ primaryColor: '#ff0000' }));
    const { loadBranding } = await import('./branding');
    loadBranding();
    expect(document.documentElement.style.setProperty).toHaveBeenCalledWith('--brand-primary', '#ff0000');
  });

  it('defaults survive invalid JSON in localStorage', async () => {
    localStorage.setItem('argus_branding', 'not-json');
    const { getBrand, loadBranding } = await import('./branding');
    loadBranding();
    expect(getBrand().appName).toBe('Argus');
  });
});
