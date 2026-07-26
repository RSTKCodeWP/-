/**
 * ESLint configuration for the TerraForge Studio frontend.
 *
 * `npm run lint` (also used by CI) previously failed with "couldn't find a
 * configuration file" because this file was missing even though the plugins
 * were installed.
 */
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['@typescript-eslint', 'react-refresh'],
  ignorePatterns: [
    'dist',
    'dev-dist',
    'coverage',
    'node_modules',
    'src-tauri',
    'public',
    'scripts',
    '*.config.js',
    '*.config.ts',
    '*.cjs',
  ],
  rules: {
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

    // Unused identifiers are errors, but a leading underscore marks an
    // intentional discard (destructuring rest, unused callback args).
    '@typescript-eslint/no-unused-vars': [
      'error',
      {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
        ignoreRestSiblings: true,
      },
    ],
    'no-unused-vars': 'off',

    // This codebase talks to loosely-typed APIs and third-party map libraries;
    // `any` is flagged for review rather than blocking the build.
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-empty-function': 'warn',

    'no-console': ['warn', { allow: ['warn', 'error', 'info'] }],
    eqeqeq: ['error', 'smart'],
    'prefer-const': 'error',
  },
  overrides: [
    {
      files: ['**/*.test.ts', '**/*.test.tsx', 'src/test/**', 'e2e/**'],
      env: { node: true },
      rules: {
        'no-console': 'off',
        '@typescript-eslint/no-explicit-any': 'off',
        // Test doubles are deliberately empty; a body would only add noise.
        '@typescript-eslint/no-empty-function': 'off',
      },
    },
  ],
};
