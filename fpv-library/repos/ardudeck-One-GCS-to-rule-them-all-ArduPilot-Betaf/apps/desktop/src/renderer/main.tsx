import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { DetachedRoot } from './detached/DetachedRoot';
import './styles/globals.css';

// Pop-out windows share this same renderer bundle/entry. The main window opens
// `index.html` with no query; detached pop-outs open it with `?detached=1&…`
// and the component-registry chooses what to render. This avoids a second Vite
// entry and keeps Zustand/Tailwind/etc. cached between windows.
const params = new URLSearchParams(window.location.search);
const isDetached = params.get('detached') === '1';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isDetached ? <DetachedRoot /> : <App />}
  </React.StrictMode>,
);

// Dev-only: initialize test driver IPC handlers (main window only — pop-outs
// don't need test driver hooks). Uses import.meta.env.DEV for Vite tree-shaking.
if (import.meta.env.DEV && !isDetached) {
  import('./testing/ipc-handlers');
}
