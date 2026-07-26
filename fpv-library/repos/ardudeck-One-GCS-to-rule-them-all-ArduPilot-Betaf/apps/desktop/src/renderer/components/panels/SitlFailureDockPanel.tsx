/**
 * SITL Failure Injection dockview panel wrapper.
 * Renders sensor failure toggles inside PanelContainer for the telemetry dashboard.
 */

import { PanelContainer } from './panel-utils';
import SitlFailurePanel from '../sitl/SitlFailurePanel';

export function SitlFailureDockPanel() {
  return (
    <PanelContainer>
      <SitlFailurePanel bare />
    </PanelContainer>
  );
}
