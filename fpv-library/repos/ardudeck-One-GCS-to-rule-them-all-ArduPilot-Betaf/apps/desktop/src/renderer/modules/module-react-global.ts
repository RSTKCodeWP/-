import * as React from 'react';
import * as ReactDomClient from 'react-dom/client';

declare global {
  interface Window {
    __ardudeckHost?: {
      react: typeof React;
      reactDom: typeof ReactDomClient;
    };
  }
}

export function installReactGlobal(): void {
  window.__ardudeckHost = { react: React, reactDom: ReactDomClient };
}
