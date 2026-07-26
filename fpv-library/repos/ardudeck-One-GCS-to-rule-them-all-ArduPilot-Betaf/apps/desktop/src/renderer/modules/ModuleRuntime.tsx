import { createContext, useContext, useEffect, useState, type ReactNode, type ComponentType } from 'react';
import { installReactGlobal } from './module-react-global';
import { createRendererHostApi } from './module-host-renderer';

interface MountEntry {
  slug: string;
  component: ComponentType;
}

type MountMap = Record<string, MountEntry[]>;

interface RuntimeContextValue {
  mounts: MountMap;
}

const RuntimeContext = createContext<RuntimeContextValue>({ mounts: {} });

export function useMountPoint(name: string): MountEntry[] {
  return useContext(RuntimeContext).mounts[name] ?? [];
}

interface RendererExports {
  activate?: (host: ReturnType<typeof createRendererHostApi>) => void | Promise<void>;
  deactivate?: () => void | Promise<void>;
}

interface LoadedModuleInfo {
  slug: string;
  manifest: { entry?: { renderer?: string } } | null;
  installPath: string;
}

export function ModuleRuntime({ children }: { children: ReactNode }) {
  const [mounts, setMounts] = useState<MountMap>({});

  useEffect(() => {
    installReactGlobal();

    const register = (slug: string, name: string, component: ComponentType) => {
      setMounts((prev) => {
        const existing = prev[name] ?? [];
        const filtered = existing.filter((e) => e.slug !== slug);
        return { ...prev, [name]: [...filtered, { slug, component }] };
      });
    };

    (async () => {
      const loaded = (await window.electronAPI.moduleHostListLoaded()) as LoadedModuleInfo[];
      console.log(`[ModuleRuntime] ${loaded.length} loaded module(s) reported by host`);
      for (const rec of loaded) {
        const rendererEntry = rec.manifest?.entry?.renderer;
        if (!rendererEntry) continue;
        // Custom protocol registered in main so Electron's webSecurity allows
        // dynamic-import from the vite-served renderer.
        const url = `ardudeck-module://${rec.slug}/${rendererEntry}`;
        console.log(`[ModuleRuntime] loading ${rec.slug} from ${url}`);
        try {
          const mod = (await import(/* @vite-ignore */ url)) as RendererExports;
          if (typeof mod.activate === 'function') {
            const host = createRendererHostApi(rec.slug, register);
            await mod.activate(host);
            console.log(`[ModuleRuntime] activated ${rec.slug}`);
          } else {
            console.warn(`[ModuleRuntime] ${rec.slug} has no activate() export`);
          }
        } catch (err) {
          console.error(`[ModuleRuntime] failed to load ${rec.slug}:`, err);
        }
      }
    })();
  }, []);

  return <RuntimeContext.Provider value={{ mounts }}>{children}</RuntimeContext.Provider>;
}
