/**
 * Auth slice for the persisted settings store. The settings store does not
 * own any auth state today. Auth tokens, session, and sign-in state live
 * in the dedicated `auth-store.ts`. This file exists as a documented
 * placeholder so the slice file layout stays symmetric with the other
 * domain slices and so future auth-related settings (remember-me, default
 * sign-in flow, last-known-user) have an obvious home.
 *
 * @license GPL-3.0-only
 */

import type { SettingsSliceFactory, SettingsStoreState } from "./types";

export const authDefaults: Partial<SettingsStoreState> = {};

export const createAuthActions: SettingsSliceFactory<
  Record<string, never>
> = () => ({});
