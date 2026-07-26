import type { MainHostApi } from '@ardudeck/module-sdk';

export async function activate(host: MainHostApi) {
  host.log('info', '__NAME__ main-side activated');
}

export function deactivate() {}
