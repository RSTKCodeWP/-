import type { Plugin } from 'esbuild';

const HOST_GLOBAL_MAP: Record<string, string> = {
  'react': 'window.__ardudeckHost.react',
  'react-dom': 'window.__ardudeckHost.reactDom',
  'react-dom/client': 'window.__ardudeckHost.reactDom',
};

export function ardudeckModulePlugin(): Plugin {
  return {
    name: 'ardudeck-module-host-externals',
    setup(build) {
      const escaped = Object.keys(HOST_GLOBAL_MAP)
        .map((s) => s.replace(/\//g, '\\/'))
        .join('|');
      const filter = new RegExp(`^(${escaped})$`);
      build.onResolve({ filter }, (args) => ({
        path: args.path,
        namespace: 'ardudeck-host-ext',
      }));
      build.onLoad({ filter: /.*/, namespace: 'ardudeck-host-ext' }, (args) => {
        const target = HOST_GLOBAL_MAP[args.path];
        if (!target) return { contents: '', loader: 'js' };
        return {
          contents: `module.exports = ${target};`,
          loader: 'js',
        };
      });
    },
  };
}
