/** @type {import('tailwindcss').Config} */
// Same token contract as apps/desktop/tailwind.config.js. The CSS variables behind these
// names are defined in src/renderer/styles/globals.css, so a component written for one app
// renders the same in the other.
export default {
  content: ['./src/renderer/**/*.{html,tsx,ts}'],
  theme: {
    extend: {
      colors: {
        surface: {
          base: 'var(--bg-base)',
          DEFAULT: 'var(--bg-surface)',
          raised: 'var(--bg-surface-raised)',
          inset: 'var(--bg-inset)',
          input: 'var(--bg-input)',
          nav: 'var(--bg-nav)',
          tooltip: 'var(--bg-tooltip)',
          overlay: 'var(--bg-overlay)',
          'overlay-light': 'var(--bg-overlay-light)',
          'overlay-subtle': 'var(--bg-overlay-subtle)',
          solid: 'var(--bg-solid)',
        },
        content: {
          DEFAULT: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
          disabled: 'var(--text-disabled)',
        },
      },
      borderColor: {
        DEFAULT: 'var(--border-default)',
        subtle: 'var(--border-subtle)',
        strong: 'var(--border-strong)',
      },
      ringOffsetColor: {
        DEFAULT: 'var(--ring-offset)',
      },
      boxShadowColor: {
        DEFAULT: 'var(--shadow-color)',
      },
    },
  },
  plugins: [],
};
