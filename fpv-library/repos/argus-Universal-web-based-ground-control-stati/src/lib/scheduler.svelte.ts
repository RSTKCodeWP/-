/**
 * App-level mission scheduler — ticks for the whole GCS session, not just
 * while SchedulerPanel is open (the panel is only a UI over this store).
 *
 * Safety model: a due schedule NEVER auto-starts the mission. Every firing
 * pops the standard confirm dialog (repo convention: every call path to
 * mission_start guards on confirm) — the scheduler is a reminder + one-click
 * runner, not an unattended autostart. A due tick also never steals a dialog
 * the user is already looking at; it waits for the next tick instead.
 */

import { app, addToast, confirmState, showConfirm } from './stores.svelte';
import { dispatch } from './transport';
import { t } from './i18n.svelte';

export type Frequency = 'once' | 'daily' | 'weekly' | 'custom';
export type ScheduleStatus = 'pending' | 'completed';

export interface Schedule {
  id: number;
  name: string;
  frequency: Frequency;
  customHours: number;
  /** datetime-local string, e.g. "2026-07-13T18:30" */
  startTime: string;
  autoArm: boolean;
  status: ScheduleStatus;
}

const STORAGE_KEY = 'argus_schedules';
const LOCK_KEY = 'argus_sched_lock';
const TICK_MS = 15000;
const LOCK_STALE_MS = 60000;

export const schedulerState = $state({ schedules: [] as Schedule[] });

const tabId = Math.random().toString(36).slice(2);

function load(): Schedule[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      // Drop the legacy missionName field (saved-mission slots never existed)
      // and the legacy 'active' status.
      if (Array.isArray(parsed)) {
        return parsed.map((s) => ({
          id: s.id,
          name: s.name,
          frequency: s.frequency ?? 'once',
          customHours: s.customHours ?? 24,
          startTime: s.startTime ?? '',
          autoArm: !!s.autoArm,
          status: s.status === 'completed' ? 'completed' : 'pending',
        }));
      }
    }
  } catch {
    /* corrupted storage — start empty */
  }
  return [];
}

export function persistSchedules(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(schedulerState.schedules));
  } catch {
    /* quota/private mode — schedule stays in memory */
  }
}

export function addSchedule(s: Omit<Schedule, 'id' | 'status'>): void {
  schedulerState.schedules.push({ ...s, id: Date.now(), status: 'pending' });
  persistSchedules();
}

export function deleteSchedule(id: number): void {
  const idx = schedulerState.schedules.findIndex((s) => s.id === id);
  if (idx >= 0) {
    schedulerState.schedules.splice(idx, 1);
    persistSchedules();
  }
}

function fmtLocal(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** Advance a repeating schedule past `now` (catch-up so a long-closed GCS
 * doesn't replay every missed occurrence); mark 'once' completed.
 * daily/weekly step by CALENDAR days so the wall-clock time survives DST;
 * custom steps by duration (hours are hours). */
export function advanceSchedule(s: Schedule, now: number): void {
  if (s.frequency === 'once') {
    s.status = 'completed';
    return;
  }
  const d = new Date(Date.parse(s.startTime));
  while (d.getTime() <= now) {
    if (s.frequency === 'daily') d.setDate(d.getDate() + 1);
    else if (s.frequency === 'weekly') d.setDate(d.getDate() + 7);
    else d.setTime(d.getTime() + Math.max(1, s.customHours) * 3600_000);
  }
  s.startTime = fmtLocal(d);
}

export type FireResult = 'fired' | 'declined' | 'stolen';

/** Confirm-gated firing shared by the timer and the panel's run-now button.
 * 'stolen' means another showConfirm caller (RTL keybind, mission clear, …)
 * replaced our dialog and resolved it as false — the caller MUST NOT advance
 * the schedule in that case (it was never actually offered to the user), or a
 * routine unrelated action would silently mark a due mission completed. */
export async function fireSchedule(s: Schedule): Promise<FireResult> {
  const note = s.autoArm ? t('sched.withAutoArm') : '';
  const ok = await showConfirm(`${s.name}: ${t('sched.confirmRun')}${note}`, true);
  if (!ok) {
    // showConfirm's steal path resolves the old promise false and immediately
    // makes its own dialog visible; a genuine decline sets visible=false. So a
    // false with a dialog still up means ours was stolen, not declined.
    if (confirmState.visible) return 'stolen';
    addToast(t('sched.skippedDeclined'), 'info');
    return 'declined';
  }
  if (s.autoArm && !app.drone.armed) {
    dispatch('arm');
    // Give the FC a moment to arm before AUTO — same fire-and-observe model
    // as the manual flow (any failure surfaces via cmd_ack/statustext events).
    await new Promise((r) => setTimeout(r, 2000));
  }
  dispatch('mission_start');
  addToast(t('sched.started'), 'success');
  return 'fired';
}

/** One tab fires at a time: localStorage lease, stolen only when stale.
 * Two tabs of the same browser share schedules — without this both would
 * pop a confirm for the same due entry (double mission_start). */
function acquireFireLock(now: number): boolean {
  try {
    const raw = localStorage.getItem(LOCK_KEY);
    if (raw) {
      const [owner, ts] = raw.split(':');
      if (owner !== tabId && now - Number(ts) < LOCK_STALE_MS) return false;
    }
    localStorage.setItem(LOCK_KEY, `${tabId}:${now}`);
    return true;
  } catch {
    return true; // no storage — single-tab semantics anyway
  }
}

function releaseFireLock(): void {
  try {
    const raw = localStorage.getItem(LOCK_KEY);
    if (raw && raw.startsWith(`${tabId}:`)) localStorage.removeItem(LOCK_KEY);
  } catch {
    /* ignore */
  }
}

let timer: ReturnType<typeof setInterval> | null = null;
let firing = false;

async function tick(): Promise<void> {
  if (firing) {
    // Our confirm is still up. Renew the lease so a peer tab doesn't treat it
    // as stale (LOCK_STALE_MS) and steal it mid-confirm — the await can sit
    // for minutes on a mission-start decision.
    try {
      localStorage.setItem(LOCK_KEY, `${tabId}:${Date.now()}`);
    } catch {
      /* no storage */
    }
    return;
  }
  // Never replace a dialog the user is interacting with (showConfirm would
  // decline-and-replace it) — the schedule stays due, next tick retries.
  if (confirmState.visible) return;
  const tickNow = Date.now();
  if (!acquireFireLock(tickNow)) return;
  try {
    // Snapshot: fireSchedule can await for minutes and the user may
    // add/delete schedules from the panel meanwhile.
    for (const s of [...schedulerState.schedules]) {
      if (s.status !== 'pending') continue;
      const due = Date.parse(s.startTime);
      if (Number.isNaN(due) || tickNow < due) continue;
      if (!schedulerState.schedules.includes(s)) continue; // deleted mid-round
      if (!app.drone.connected) {
        addToast(`${s.name}: ${t('sched.skippedOffline')}`, 'warn', 6000);
        advanceSchedule(s, Date.now());
        persistSchedules();
        continue;
      }
      firing = true;
      let result: FireResult;
      try {
        result = await fireSchedule(s);
      } finally {
        firing = false;
      }
      // Stolen: another dialog replaced ours; the schedule was never offered.
      // Leave it pending — the next tick retries once that dialog closes.
      if (result === 'stolen') continue;
      // Compare by id, not reference: an onStorage reload (peer-tab edit)
      // rebuilds the array with fresh objects, so `s` may no longer be ===
      // any element even though the schedule still exists. Mutate the live one.
      const current = schedulerState.schedules.find((x) => x.id === s.id);
      if (!current) continue; // genuinely deleted while confirming
      // Fresh clock: the confirm may have sat open longer than the repeat
      // interval — advancing from the stale tick time would leave startTime
      // in the past and refire within 15s (double mission_start).
      advanceSchedule(current, Date.now());
      persistSchedules();
    }
  } finally {
    releaseFireLock();
  }
}

function onStorage(e: StorageEvent): void {
  // Another tab edited the schedule list — reload instead of clobbering it
  // on our next persist (deleted schedules used to resurrect this way).
  if (e.key === STORAGE_KEY) schedulerState.schedules = load();
}

export function startScheduler(): void {
  if (timer) return;
  schedulerState.schedules = load();
  timer = setInterval(() => void tick(), TICK_MS);
  try {
    window.addEventListener('storage', onStorage);
  } catch {
    /* non-browser test env */
  }
}

export function stopScheduler(): void {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  try {
    window.removeEventListener('storage', onStorage);
  } catch {
    /* non-browser test env */
  }
}
