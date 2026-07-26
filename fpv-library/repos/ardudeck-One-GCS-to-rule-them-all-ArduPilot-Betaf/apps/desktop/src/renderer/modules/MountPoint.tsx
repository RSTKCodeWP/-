import { useMountPoint } from './ModuleRuntime';

export function MountPoint({ name }: { name: string }) {
  const entries = useMountPoint(name);
  return (
    <>
      {entries.map(({ slug, component: Comp }) => (
        <Comp key={slug} />
      ))}
    </>
  );
}
