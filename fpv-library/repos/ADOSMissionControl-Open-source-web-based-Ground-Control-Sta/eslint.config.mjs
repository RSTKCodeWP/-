import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  ...nextCoreWebVitals,
  {
    ignores: [
      "convex/_generated/**",
      "convex-tutorial/**",
      "coverage/**",
      "release/**",
      // Vendored, minified third-party bundles copied into public/ at build
      // time. They are not our source and trip rules-of-hooks on their own
      // minified identifiers, so linting them is noise.
      "public/cesium/**",
      "public/monaco-vs/**",
    ],
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "react-hooks/immutability": "warn",
      "react-hooks/preserve-manual-memoization": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/static-components": "warn",
    },
  },
  {
    // Test files mount throwaway stub components (icon and child mocks) that
    // never reach a real render tree, so a missing display name is harmless.
    files: ["tests/**/*.{ts,tsx}", "src/**/__tests__/**/*.{ts,tsx}"],
    rules: {
      "react/display-name": "off",
    },
  },
];

export default eslintConfig;
