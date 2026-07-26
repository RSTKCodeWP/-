/**
 * SITL Environment dockview panel wrapper.
 * Renders wind/battery controls inside PanelContainer for the telemetry dashboard.
 */

import { PanelContainer } from './panel-utils';
import SitlEnvironmentPanel from '../sitl/SitlEnvironmentPanel';

export function SitlEnvironmentDockPanel() {
  return (
    <PanelContainer>
      <SitlEnvironmentPanel bare />
    </PanelContainer>
  );
}
