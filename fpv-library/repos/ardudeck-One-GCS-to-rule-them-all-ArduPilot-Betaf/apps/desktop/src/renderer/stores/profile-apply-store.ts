import { create } from 'zustand';
import type { VehicleProfile } from './settings-store.js';
import type { FileParamDiff } from './parameter-store.js';
import type { ProfileSnapshot } from '../lib/vehicle-templates/types.js';

export interface ProfileApplyToast {
  kind: 'success' | 'error' | 'info';
  message: string;
  snapshotId?: string;   // present for success; enables one-click Undo
  profileId?: string;    // which profile was applied (for Undo routing)
  rebootRequired?: number;
  createdAt: number;
}

/**
 * Pre-flight bundle for real-FC applies. Kept at the store level so the
 * "are you sure?" modal survives Edit Vehicle closing.
 */
export interface ProfileApplyPreflight {
  profile: VehicleProfile;
  fileDiffs: FileParamDiff[];
  pendingSnapshot: ProfileSnapshot;
  destructiveParams: string[];
  target: { isSitl: boolean; sysid: number; label: string };
}

export type ProfileApplyStatus = 'idle' | 'reviewing' | 'writing' | 'done';

interface ProfileApplyStore {
  /** Where in the apply lifecycle we currently are. */
  status: ProfileApplyStatus;
  /** Profile ID currently being applied (lets the card/edit show an in-flight indicator). */
  activeProfileId: string | null;
  /** Pending real-FC confirmation modal, if any. */
  preflight: ProfileApplyPreflight | null;
  /** Persistent toast (rendered at App root so it survives view + modal changes). */
  toast: ProfileApplyToast | null;

  setStatus: (status: ProfileApplyStatus, profileId?: string | null) => void;
  setPreflight: (p: ProfileApplyPreflight | null) => void;
  setToast: (toast: ProfileApplyToast | null) => void;
  clear: () => void;
}

export const useProfileApplyStore = create<ProfileApplyStore>((set) => ({
  status: 'idle',
  activeProfileId: null,
  preflight: null,
  toast: null,

  setStatus: (status, profileId) =>
    set({ status, activeProfileId: profileId !== undefined ? profileId : null }),
  setPreflight: (preflight) => set({ preflight }),
  setToast: (toast) => set({ toast }),
  clear: () => set({ status: 'idle', activeProfileId: null, preflight: null }),
}));
