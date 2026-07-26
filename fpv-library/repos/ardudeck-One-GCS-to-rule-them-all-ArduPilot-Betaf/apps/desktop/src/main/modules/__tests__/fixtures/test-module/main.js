export function activate(host) {
  host.log('info', 'activated', host.moduleSlug);
  return { activated: true };
}
