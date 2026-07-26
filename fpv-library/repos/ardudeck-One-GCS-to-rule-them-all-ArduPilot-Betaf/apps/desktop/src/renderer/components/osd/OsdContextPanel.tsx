/**
 * OSD Context Panel
 *
 * Right-side panel. Its content follows what the user is doing:
 * - An element is selected -> fine position editor for that element.
 * - Otherwise, the preview's data controls: demo sliders, or live status.
 */

import type { OsdElementKey } from '../../stores/osd-store';
import type { OsdDataSource } from '../../stores/osd-store';
import { OsdDemoPanel } from './OsdDemoPanel';
import { OsdLivePanel } from './OsdLivePanel';
import { OsdEditPanel } from './OsdEditPanel';

interface Props {
  dataSource: OsdDataSource;
  selectedElement: OsdElementKey | null;
  onClearSelection: () => void;
}

export function OsdContextPanel({ dataSource, selectedElement, onClearSelection }: Props) {
  if (selectedElement) {
    return <OsdEditPanel selectedElement={selectedElement} onDone={onClearSelection} />;
  }
  if (dataSource === 'live') {
    return <OsdLivePanel />;
  }
  return <OsdDemoPanel />;
}
