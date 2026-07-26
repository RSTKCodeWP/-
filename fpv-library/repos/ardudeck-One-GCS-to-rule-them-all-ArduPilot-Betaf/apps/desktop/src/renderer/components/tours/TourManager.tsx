import { useEffect } from 'react';
import { useNavigationStore } from '../../stores/navigation-store';
import { useConnectionStore } from '../../stores/connection-store';
import { useToursStore, isTourEligible } from '../../stores/tours-store';
import { useTelemetryLayoutStore } from '../../stores/telemetry-layout-store';
import { getToursForView, getTourById } from '../../feature-tours';
import type { FeatureTour } from '../../feature-tours';
import { isPanelVisible } from '../../feature-tours/panel-selectors';
import type { PanelId } from '../panels';
import { TourPrompt } from './TourPrompt';
import { ActiveTour } from './ActiveTour';
import { TourLaunchGate } from './TourLaunchGate';
import { TourPanelsGate } from './TourPanelsGate';

const PROMPT_DELAY_MS = 800;
const PENDING_START_DELAY_MS = 400;
const PANEL_SETTLE_DELAY_MS = 200;

function requiresConnection(tour: FeatureTour): boolean {
  return tour.requires?.connection === true;
}

function missingPanels(tour: FeatureTour): PanelId[] {
  const required = tour.requires?.panels ?? [];
  if (required.length === 0) return [];
  return required.filter((id) => !isPanelVisible(id));
}

export function TourManager() {
  const currentView = useNavigationStore((s) => s.currentView);
  const setView = useNavigationStore((s) => s.setView);
  const isConnected = useConnectionStore((s) => s.connectionState.isConnected);

  const promptTourId = useToursStore((s) => s.promptTourId);
  const activeTourId = useToursStore((s) => s.activeTourId);
  const pendingTourId = useToursStore((s) => s.pendingTourId);
  const gateTourId = useToursStore((s) => s.gateTourId);
  const panelGateTourId = useToursStore((s) => s.panelGateTourId);
  const showPrompt = useToursStore((s) => s.showPrompt);
  const dismissPrompt = useToursStore((s) => s.dismissPrompt);
  const markSeen = useToursStore((s) => s.markSeen);
  const skipForSession = useToursStore((s) => s.skipForSession);
  const setActiveTour = useToursStore((s) => s.setActiveTour);
  const setPendingTour = useToursStore((s) => s.setPendingTour);
  const setGateTour = useToursStore((s) => s.setGateTour);
  const setPanelGateTour = useToursStore((s) => s.setPanelGateTour);

  // Schedule a prompt for the first eligible tour on this view.
  useEffect(() => {
    const candidates = getToursForView(currentView);
    if (candidates.length === 0) return;
    const state = useToursStore.getState();
    // Tour-level predicate gates whether a tour is offered at all (e.g. the
    // QuadPlane VTOL switch only applies when both controller sets exist).
    const next = candidates.find(
      (t) => isTourEligible(t.id, state) && (!t.predicate || t.predicate()),
    );
    if (!next) return;
    if (state.activeTourId || state.gateTourId || state.panelGateTourId) return;
    const timer = setTimeout(() => showPrompt(next.id), PROMPT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [currentView, showPrompt]);

  // Auto-start tour when connection comes up (user chose "use my own FC").
  useEffect(() => {
    if (!pendingTourId || !isConnected) return;
    const tour = getTourById(pendingTourId);
    if (!tour) {
      setPendingTour(null);
      return;
    }
    const id = window.setTimeout(() => {
      setPendingTour(null);
      if (tour.view !== useNavigationStore.getState().currentView) {
        setView(tour.view);
      }
      window.setTimeout(() => continueToPanelsGateOrStart(tour), 250);
    }, PENDING_START_DELAY_MS);
    return () => window.clearTimeout(id);
  }, [pendingTourId, isConnected, setPendingTour, setView]);

  const promptTour = promptTourId ? getTourById(promptTourId) : null;
  const activeTour = activeTourId ? getTourById(activeTourId) : null;
  const gateTour = gateTourId ? getTourById(gateTourId) : null;
  const panelGateTour = panelGateTourId ? getTourById(panelGateTourId) : null;

  const continueToPanelsGateOrStart = (tour: FeatureTour) => {
    const stillMissing = missingPanels(tour);
    if (stillMissing.length > 0 && tour.requires?.preset) {
      setPanelGateTour(tour.id);
      return;
    }
    markSeen(tour.id);
    setActiveTour(tour.id);
  };

  const startTour = (tour: FeatureTour) => {
    const go = () => continueToPanelsGateOrStart(tour);
    if (tour.view !== currentView) {
      setView(tour.view);
      window.setTimeout(go, 250);
    } else {
      go();
    }
  };

  const handleAccept = () => {
    if (!promptTour) return;
    dismissPrompt();

    if (requiresConnection(promptTour) && !isConnected) {
      setGateTour(promptTour.id);
      return;
    }
    startTour(promptTour);
  };

  const handleDecline = () => {
    if (!promptTour) return;
    markSeen(promptTour.id);
    dismissPrompt();
  };

  const handleLater = () => {
    if (!promptTour) return;
    skipForSession(promptTour.id);
    dismissPrompt();
  };

  const handleAdvanceToTour = (nextTourId: string) => {
    const next = getTourById(nextTourId);
    if (!next) return;

    if (requiresConnection(next) && !isConnected) {
      setGateTour(nextTourId);
      return;
    }
    startTour(next);
  };

  // Connection gate handlers
  const handleGateLaunched = () => {
    if (!gateTour) return;
    const tour = gateTour;
    setGateTour(null);
    startTour(tour);
  };

  const handleGateUseOwnFc = () => {
    if (!gateTour) return;
    setPendingTour(gateTour.id);
    setGateTour(null);
  };

  const handleGateInstallSitl = () => {
    if (!gateTour) return;
    setPendingTour(gateTour.id);
    setGateTour(null);
    setView('sitl');
  };

  const handleGateCancel = () => {
    if (!gateTour) return;
    skipForSession(gateTour.id);
    setGateTour(null);
  };

  // Panels gate handlers
  const handlePanelGateSwitch = () => {
    if (!panelGateTour) return;
    const bridge = useTelemetryLayoutStore.getState().bridge;
    const tour = panelGateTour;
    setPanelGateTour(null);
    const preset = tour.requires?.preset;
    if (bridge && preset) {
      bridge.loadPreset(preset);
    }
    // Let the preset settle before probing selectors again.
    window.setTimeout(() => {
      markSeen(tour.id);
      setActiveTour(tour.id);
    }, PANEL_SETTLE_DELAY_MS);
  };

  const handlePanelGateCancel = () => {
    if (!panelGateTour) return;
    skipForSession(panelGateTour.id);
    setPanelGateTour(null);
  };

  return (
    <>
      {promptTour && !activeTour && !gateTour && !panelGateTour && (
        <TourPrompt
          tour={promptTour}
          onAccept={handleAccept}
          onDecline={handleDecline}
          onLater={handleLater}
        />
      )}
      {gateTour && (
        <TourLaunchGate
          tour={gateTour}
          onLaunched={handleGateLaunched}
          onUseOwnFc={handleGateUseOwnFc}
          onInstallSitl={handleGateInstallSitl}
          onCancel={handleGateCancel}
        />
      )}
      {panelGateTour && (
        <TourPanelsGate
          tour={panelGateTour}
          missingPanels={missingPanels(panelGateTour)}
          onSwitchPreset={handlePanelGateSwitch}
          onCancel={handlePanelGateCancel}
        />
      )}
      {activeTour && (
        <ActiveTour
          key={activeTour.id}
          tour={activeTour}
          onFinish={() => setActiveTour(null)}
          onAdvanceToTour={handleAdvanceToTour}
        />
      )}
    </>
  );
}
