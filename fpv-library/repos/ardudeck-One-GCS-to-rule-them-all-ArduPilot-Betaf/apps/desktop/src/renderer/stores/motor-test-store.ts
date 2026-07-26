import { create } from 'zustand';

interface MotorTestStore {
  /** Throttle percent (0-100) */
  throttle: number;
  /** Test duration per motor, seconds */
  duration: number;
  /** Motor currently being tested (1-based), null if idle */
  activeMotor: number | null;
  /** True while a "Test All In Sequence" or "Test All" run is in progress */
  sequenceRunning: boolean;
  /** User confirmed props removed for this session */
  safetyConfirmed: boolean;
  /** Last error message from a test command, null if none */
  lastError: string | null;

  setThrottle: (value: number) => void;
  setDuration: (value: number) => void;
  setActiveMotor: (motor: number | null) => void;
  setSequenceRunning: (running: boolean) => void;
  confirmSafety: () => void;
  setLastError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  throttle: 8,
  duration: 3,
  activeMotor: null as number | null,
  sequenceRunning: false,
  safetyConfirmed: false,
  lastError: null as string | null,
};

export const useMotorTestStore = create<MotorTestStore>((set) => ({
  ...initialState,

  setThrottle: (value) => set({ throttle: Math.max(0, Math.min(100, value)) }),
  setDuration: (value) => set({ duration: Math.max(1, Math.min(60, value)) }),
  setActiveMotor: (motor) => set({ activeMotor: motor }),
  setSequenceRunning: (running) => set({ sequenceRunning: running }),
  confirmSafety: () => set({ safetyConfirmed: true }),
  setLastError: (error) => set({ lastError: error }),
  reset: () => set(initialState),
}));
