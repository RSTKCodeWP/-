import { useEffect } from 'react';
import { useLauncherStore } from './stores/launcher-store';
import { TopBar } from './components/TopBar';
import { StepRail } from './components/StepRail';
import { RegionStep } from './components/RegionStep';
import { PlaceholderStep } from './components/PlaceholderStep';
import { SummaryPanel } from './components/SummaryPanel';
import { GameLogPanel } from './components/GameLogPanel';

export default function App() {
  const init = useLauncherStore((s) => s.init);
  const step = useLauncherStore((s) => s.step);
  const setStep = useLauncherStore((s) => s.setStep);
  const selectedRegion = useLauncherStore((s) => s.selectedRegion);

  useEffect(() => {
    void init();
  }, [init]);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <StepRail step={step} onStep={setStep} regionChosen={Boolean(selectedRegion)} />
        <main className="min-w-0 flex-1 overflow-y-auto p-4">
          {step === 'region' && <RegionStep />}
          {step === 'conditions' && (
            <PlaceholderStep
              title="Conditions"
              summary="Time of day and weather become selections here, either the real clock and real weather for the region, or a chosen setting."
              items={[
                'The sun is already true solar position from latitude and day of year, so a real clock drives it directly.',
                'Weather presets (clear, fair, overcast, storm) already interpolate smoothly. Nothing drives them yet.',
                'The in-game keys stay as debug overrides once this step is real.',
              ]}
            />
          )}
          {step === 'vehicle' && (
            <PlaceholderStep
              title="Vehicle"
              summary="Firmware, frame and your own parameter file are chosen here, so you test-fly the aircraft you actually own."
              items={[
                'Firmware family and release track, with SITL fetched if it is missing.',
                'Frame selection, reading the same frame JSON ArduDeck writes.',
                'Real parameter import, filtered for SITL safety, with FRAME_CLASS and FRAME_TYPE carried through so the simulated motor layout matches what the flight stack is mixing for.',
              ]}
            />
          )}
          <GameLogPanel />
        </main>
        <SummaryPanel />
      </div>
    </div>
  );
}
