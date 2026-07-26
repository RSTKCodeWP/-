/** Reset all Zustand stores between tests. */

// Import stores that need resetting
// NOTE: Only import stores as they're needed in tests
export function resetAllStores(): void {
  // Zustand v5 stores expose setState/getState directly
  // Individual test files should import and reset stores they use
}
