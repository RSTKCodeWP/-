import { getTemplate } from '../../../lib/vehicle-templates/registry.js';

interface TemplateChipProps {
  slug: string | undefined;
}

/** Small pill showing which template seeded/owns this profile. */
export function TemplateChip({ slug }: TemplateChipProps) {
  const tpl = getTemplate(slug);
  if (!tpl) return null;
  const Icon = tpl.icon;
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-300 border border-blue-500/20"
      title={tpl.description}
    >
      <Icon className="w-2.5 h-2.5" />
      {tpl.name}
    </span>
  );
}
