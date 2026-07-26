import type { RendererHostApi } from '@ardudeck/module-sdk';

function FloatingPanel({ host: _host }: { host: RendererHostApi }) {
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 9999,
        padding: '8px 12px',
        background: '#1a1a1a',
        color: '#fff',
        borderRadius: 8,
        fontSize: 12,
        border: '1px solid #333',
      }}
    >
      __NAME__
    </div>
  );
}

export async function activate(host: RendererHostApi) {
  host.log('info', '__NAME__ renderer activated');
  host.registerMountPoint('floatingOverlay', () => <FloatingPanel host={host} />);
}

export function deactivate() {}
