import type { ComponentType } from 'react';
import type { RendererHostApi, MountPointName, HudProjection } from '@ardudeck/module-sdk';
import { useTelemetryStore } from '../stores/telemetry-store';
import { useConnectionStore } from '../stores/connection-store';
import { useNavigationStore } from '../stores/navigation-store';
import { useParameterStore } from '../stores/parameter-store';
import { useMissionStore } from '../stores/mission-store';
import { useCommandTargetStore, SELF_VEHICLE_ID } from '../stores/command-target-store';
import { useHudStore } from '../stores/hud-store';
import { useHudOverlayStore } from '../stores/hud-overlay-store';
import { buildHudProjection } from '../components/camera/hud/hud-projection';
import {
  registerModuleOsdElement,
  unregisterModuleOsdElement,
} from './module-osd-registry';
import {
  registerModuleHudInstrument,
  unregisterModuleHudInstrument,
} from './module-hud-registry';
import {
  registerModulePanel,
  unregisterModulePanel,
} from './module-panel-registry';
import {
  registerSurveyGenerator,
  unregisterSurveyGenerator,
  type SurveyGeneratorRegistration,
} from '../components/survey/generator-registry';

type RegisterFn = (slug: string, name: MountPointName, component: ComponentType) => void;

function currentHudProjection(): HudProjection | null {
  if (!useHudOverlayStore.getState().active) return null;
  return buildHudProjection(useHudStore.getState().config);
}

// Which generator ids each module registered, so a module can only remove its
// own and a future module-unload path can sweep them all.
const surveyGeneratorsBySlug = new Map<string, Set<string>>();

/** Remove every survey generator a module registered (module unload/reload). */
export function unregisterModuleSurveyGenerators(slug: string): void {
  const ids = surveyGeneratorsBySlug.get(slug);
  if (!ids) return;
  for (const id of ids) unregisterSurveyGenerator(id);
  surveyGeneratorsBySlug.delete(slug);
}

export function createRendererHostApi(
  slug: string,
  register: RegisterFn,
): RendererHostApi {
  return {
    moduleSlug: slug,

    telemetry: {
      getSnapshot: () => useTelemetryStore.getState() as unknown,
      subscribe: (listener) => useTelemetryStore.subscribe(listener as (s: unknown) => void),
    },

    connection: {
      getState: () => useConnectionStore.getState() as unknown,
      subscribe: (listener) => useConnectionStore.subscribe(listener as (s: unknown) => void),
    },

    view: {
      getCurrent: () => useNavigationStore.getState().currentView as string,
      subscribe: (listener) =>
        useNavigationStore.subscribe((s) => listener(s.currentView as string)),
    },

    params: {
      getAll: async () => {
        const state = useParameterStore.getState() as unknown as {
          parameters?: Map<string, unknown> | Record<string, unknown>;
        };
        const p = state.parameters;
        if (!p) return [];
        if (p instanceof Map) return Array.from(p.values());
        return Object.values(p);
      },
      get: async (name) => {
        const state = useParameterStore.getState() as unknown as {
          parameters?: Map<string, unknown> | Record<string, unknown>;
        };
        const p = state.parameters;
        if (!p) return undefined;
        if (p instanceof Map) return p.get(name);
        return (p as Record<string, unknown>)[name];
      },
      set: async (name, value) => {
        // Type 9 = MAV_PARAM_TYPE_REAL32 (float). Module callers must know this.
        await window.electronAPI.setParameter(name, value, 9);
      },
    },

    pty: {
      create: (opts) => window.electronAPI.moduleHostPtyCreate(slug, opts),
      write: (id, data) => window.electronAPI.moduleHostPtyWrite(id, data),
      resize: (id, cols, rows) => window.electronAPI.moduleHostPtyResize(id, cols, rows),
      kill: (id) => window.electronAPI.moduleHostPtyKill(id),
      onData: (id, cb) => window.electronAPI.moduleHostOnPtyData(id, cb),
      onExit: (id, cb) => window.electronAPI.moduleHostOnPtyExit(id, cb),
    },

    invoke: (channel, data) => window.electronAPI.moduleHostInvoke(slug, channel, data),

    hud: {
      getProjection: () => currentHudProjection(),
      subscribe: (listener) => {
        const notify = () => listener(currentHudProjection());
        const unActive = useHudOverlayStore.subscribe(notify);
        // Scale / colour / line-weight / instrument toggles live in the config store.
        const unConfig = useHudStore.subscribe(notify);
        return () => {
          unActive();
          unConfig();
        };
      },
      registerInstrument: (reg) => registerModuleHudInstrument(slug, reg),
      unregisterInstrument: (id) => unregisterModuleHudInstrument(slug, id),
      isInstrumentEnabled: (id) => useHudStore.getState().isModuleInstrumentEnabled(id),
    },

    osd: {
      registerElement: (reg) => registerModuleOsdElement(slug, reg),
      unregisterElement: (id) => unregisterModuleOsdElement(slug, id),
    },

    panels: {
      register: (reg) => registerModulePanel(slug, reg),
      unregister: (id) => unregisterModulePanel(slug, id),
    },

    mission: {
      getWaypoints: () => useMissionStore.getState().missionItems as unknown[],
      subscribe: (listener) =>
        useMissionStore.subscribe((s) => listener(s.missionItems as unknown[])),
    },

    commandTarget: {
      get: () => useCommandTargetStore.getState().targets[SELF_VEHICLE_ID] ?? null,
      subscribe: (listener) =>
        useCommandTargetStore.subscribe((s) =>
          listener(s.targets[SELF_VEHICLE_ID] ?? null),
        ),
    },

    survey: {
      registerGenerator: (reg) => {
        if (!reg?.id || reg.id.startsWith('builtin.')) {
          throw new Error(`[module:${slug}] invalid survey generator id: ${reg?.id}`);
        }
        // The SDK keeps config/result opaque so it doesn't depend on renderer
        // types; the registry owns the real SurveyConfig/SurveyResult shapes.
        registerSurveyGenerator(reg as unknown as SurveyGeneratorRegistration);
        let ids = surveyGeneratorsBySlug.get(slug);
        if (!ids) {
          ids = new Set();
          surveyGeneratorsBySlug.set(slug, ids);
        }
        ids.add(reg.id);
      },
      unregisterGenerator: (id) => {
        if (!surveyGeneratorsBySlug.get(slug)?.has(id)) return;
        unregisterSurveyGenerator(id);
        surveyGeneratorsBySlug.get(slug)?.delete(id);
      },
    },

    log: (level, ...args) => {
      const tag = `[module:${slug}]`;
      if (level === 'error') console.error(tag, ...args);
      else if (level === 'warn') console.warn(tag, ...args);
      else console.log(tag, ...args);
    },

    registerMountPoint: (name, component) => register(slug, name, component),
  };
}
