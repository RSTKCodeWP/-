export interface BrandConfig {
  appName: string;
  subtitle: string;
  logo?: string;
  primaryColor?: string;
  defaultPort?: string;
  defaultProtocol?: string;
  hideArduPilot?: boolean;
  customCss?: string;
}

const DEFAULT_BRAND: BrandConfig = {
  appName: 'Argus',
  subtitle: 'Ground Control Station',
  defaultPort: 'tcp:localhost:5770',
  defaultProtocol: 'auto',
  hideArduPilot: true,
};

let _brand: BrandConfig = { ...DEFAULT_BRAND };

export function loadBranding() {
  try {
    const el = document.getElementById('argus-branding');
    if (el) {
      const cfg = JSON.parse(el.textContent || '{}');
      _brand = { ...DEFAULT_BRAND, ...cfg };
    }
  } catch {}
  try {
    const saved = localStorage.getItem('argus_branding');
    if (saved) {
      const cfg = JSON.parse(saved);
      _brand = { ...DEFAULT_BRAND, ...cfg };
    }
  } catch {}
  if (
    _brand.primaryColor &&
    _brand.primaryColor.length < 100 &&
    !/expression|url\s*\(|javascript:|[;{}]/i.test(_brand.primaryColor)
  ) {
    document.documentElement.style.setProperty('--brand-primary', _brand.primaryColor);
  }
}

export function getBrand(): BrandConfig {
  return _brand;
}
