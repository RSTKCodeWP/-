import './app.css';
import App from './App.svelte';
import { mount } from 'svelte';

const ERROR_LOG_KEY = 'argus_error_log';
const ERROR_LOG_MAX = 50;

function logError(source: string, message: string) {
  try {
    const parsed = JSON.parse(localStorage.getItem(ERROR_LOG_KEY) || '[]');
    const log: { t: string; s: string; m: string }[] = Array.isArray(parsed) ? parsed : [];
    log.push({ t: new Date().toISOString(), s: source, m: message.slice(0, 500) });
    if (log.length > ERROR_LOG_MAX) log.splice(0, log.length - ERROR_LOG_MAX);
    localStorage.setItem(ERROR_LOG_KEY, JSON.stringify(log));
  } catch {}
}

window.addEventListener('error', (e) => {
  logError('error', `${e.message} at ${e.filename}:${e.lineno}`);
});

window.addEventListener('unhandledrejection', (e) => {
  logError('promise', String(e.reason));
});

export function getErrorLog(): { t: string; s: string; m: string }[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(ERROR_LOG_KEY) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function clearErrorLog(): void {
  localStorage.removeItem(ERROR_LOG_KEY);
}

const app = mount(App, { target: document.getElementById('app')! });

export default app;

if ('serviceWorker' in navigator) {
  navigator.serviceWorker
    .register('/sw.js')
    .then((reg) => {
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        if (!newWorker) return;
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'activated' && navigator.serviceWorker.controller) {
            newWorker.postMessage('skipWaiting');
          }
        });
      });

      const sw = reg.active || reg.waiting || reg.installing;
      if (sw && sw.state === 'activated') {
        precacheLoadedAssets(sw);
      } else if (sw) {
        sw.addEventListener('statechange', () => {
          if (sw.state === 'activated') precacheLoadedAssets(sw);
        });
      }
    })
    .catch(() => {});
}

function precacheLoadedAssets(sw: ServiceWorker) {
  const scripts = [...document.querySelectorAll<HTMLScriptElement>('script[src]')].map((s) => s.src);
  const styles = [...document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')].map((l) => l.href);
  const urls = [location.href, ...scripts, ...styles].filter((u) => u.startsWith(location.origin));
  sw.postMessage({ type: 'PRECACHE_ASSETS', urls });
}
