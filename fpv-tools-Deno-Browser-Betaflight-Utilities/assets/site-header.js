// Shared header for the FPV Tools hub and every standalone tool page.
//
// Usage:
//   <fpv-header root="./" icon="⚡" heading="FPV Tools" subtitle="..." home></fpv-header>
//   <fpv-header root="../" icon="🔀" heading="BF CLI Merge" subtitle="..."></fpv-header>
//
// `root` is the relative path back to the site root (e.g. "./" for the hub,
// "../" for a tool one level deep). It's used for the back-to-home link and
// to resolve the PWA manifest/service-worker/icons regardless of how deep
// the page lives, so every page gets install + offline support for free.
let pwaSetupDone = false;

function setupPwa(root) {
  if (pwaSetupDone) return;
  pwaSetupDone = true;

  const head = document.head;

  const manifest = document.createElement("link");
  manifest.rel = "manifest";
  manifest.href = `${root}manifest.json`;
  head.appendChild(manifest);

  const themeColor = document.createElement("meta");
  themeColor.name = "theme-color";
  themeColor.content = "#0d1117";
  head.appendChild(themeColor);

  const appleTouchIcon = document.createElement("link");
  appleTouchIcon.rel = "apple-touch-icon";
  appleTouchIcon.href = `${root}assets/icons/apple-touch-icon.png`;
  head.appendChild(appleTouchIcon);

  const icon = document.createElement("link");
  icon.rel = "icon";
  icon.href = `${root}assets/icons/icon-32.png`;
  head.appendChild(icon);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(`${root}sw.js`).catch((err) => {
      console.warn("Service worker registration failed:", err);
    });
  }
}

class FpvHeader extends HTMLElement {
  connectedCallback() {
    const root = this.getAttribute("root") ?? "./";
    const icon = this.getAttribute("icon") ?? "";
    const heading = this.getAttribute("heading") ?? "";
    const subtitle = this.getAttribute("subtitle") ?? "";
    const isHome = this.hasAttribute("home");

    this.setAttribute("role", "banner");
    this.replaceChildren();

    if (!isHome) {
      const backLink = document.createElement("a");
      backLink.className = "back-link";
      backLink.href = root;
      backLink.textContent = "← FPV Tools";
      this.appendChild(backLink);
    }

    const info = document.createElement("div");

    const h1 = document.createElement("h1");
    h1.textContent = icon ? `${icon} ${heading}` : heading;
    info.appendChild(h1);

    if (subtitle) {
      const p = document.createElement("p");
      p.textContent = subtitle;
      info.appendChild(p);
    }

    this.appendChild(info);

    setupPwa(root);
  }
}

customElements.define("fpv-header", FpvHeader);
