import { create } from 'zustand';

/**
 * Tracks long-running, potentially main-thread-blocking operations (survey
 * recompute, GIS import, etc.) so the UI can show the user what's happening
 * instead of appearing frozen. Tasks are a stack; the most recent label is what
 * the indicator shows.
 */
interface ActivityTask {
  id: number;
  label: string;
}

interface ActivityStore {
  tasks: ActivityTask[];
  begin: (label: string) => number;
  update: (id: number, label: string) => void;
  end: (id: number) => void;
}

let nextId = 1;

export const useActivityStore = create<ActivityStore>((set) => ({
  tasks: [],
  begin: (label) => {
    const id = nextId++;
    set((s) => ({ tasks: [...s.tasks, { id, label }] }));
    return id;
  },
  update: (id, label) => set((s) => ({
    tasks: s.tasks.map((t) => (t.id === id ? { ...t, label } : t)),
  })),
  end: (id) => set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),
}));

/** Resolve after the browser has had a chance to paint (double rAF). */
function nextPaint(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof requestAnimationFrame !== 'function') { resolve(); return; }
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

/**
 * Show an activity label, yield until the indicator has painted, then run the
 * work and clear the label. The paint-yield matters: heavy synchronous work
 * like a 20k-waypoint regeneration blocks the main thread, so without
 * yielding first the spinner would never render. Async work is awaited so the
 * label stays up until it settles.
 */
export async function runWithActivity<T>(label: string, work: () => T | Promise<T>): Promise<T> {
  const id = useActivityStore.getState().begin(label);
  try {
    await nextPaint();
    return await work();
  } finally {
    useActivityStore.getState().end(id);
  }
}
