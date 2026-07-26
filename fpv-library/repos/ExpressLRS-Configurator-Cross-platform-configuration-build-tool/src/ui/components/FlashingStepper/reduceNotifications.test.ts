import {
  BuildFirmwareStep,
  BuildFirmwareSubstep,
  BuildJobType,
  BuildProgressNotification,
  BuildProgressNotificationType,
  FlashingMethod,
} from '../../gql/generated/types';
import { highLevelStepsFor, reduceNotifications } from './reduceNotifications';

function n(
  type: BuildProgressNotificationType,
  step: BuildFirmwareStep,
  substep?: BuildFirmwareSubstep,
  progress?: number,
): BuildProgressNotification {
  return {
    __typename: 'BuildProgressNotification',
    type,
    step,
    substep,
    progress,
  };
}

const { Info, Error: Err, Success } = BuildProgressNotificationType;
const {
  VERIFYING_BUILD_SYSTEM,
  DOWNLOADING_FIRMWARE,
  BUILDING_FIRMWARE,
  INITIATING_PASSTHROUGH,
  FLASHING_FIRMWARE,
} = BuildFirmwareStep;

const buildPrelude: BuildProgressNotification[] = [
  n(Info, VERIFYING_BUILD_SYSTEM),
  n(Success, VERIFYING_BUILD_SYSTEM),
  n(Info, DOWNLOADING_FIRMWARE),
  n(Success, DOWNLOADING_FIRMWARE),
  n(Info, BUILDING_FIRMWARE, BuildFirmwareSubstep.CompilingFirmware),
  n(Success, BUILDING_FIRMWARE),
];

function flashingStep(notifications: BuildProgressNotification[]) {
  const { steps } = reduceNotifications(
    notifications,
    BuildJobType.Flash,
    FlashingMethod.BetaflightPassthrough,
  );
  return steps.find((s) => s.step === FLASHING_FIRMWARE)!;
}

describe('reduceNotifications', () => {
  it('incident replay: transient TargetMismatch error on a successful re-flash ends completed', () => {
    // The exact notification sequence of the "Flash another" incident: the FC
    // is still in passthrough mode, the parser (pre-fix) emitted a false
    // ERROR+TargetMismatch, then the flash proceeded to a full success. The
    // terminal SUCCESS must clear the transient error — the step ends green,
    // not as "Failed to restart device".
    const notifications = [
      ...buildPrelude,
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.DetectingDevice),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.ConnectingToDevice),
      n(Err, FLASHING_FIRMWARE, BuildFirmwareSubstep.TargetMismatch),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.ConnectingToDevice),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.ErasingFlash),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.WritingFirmware, 0),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.WritingFirmware, 50),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.WritingFirmware, 100),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.VerifyingFirmware),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.RestartingDevice),
      n(Success, FLASHING_FIRMWARE),
    ];
    const { steps, activeIdx } = reduceNotifications(
      notifications,
      BuildJobType.Flash,
      FlashingMethod.BetaflightPassthrough,
    );
    expect(steps.map((s) => s.status)).toEqual([
      'completed',
      'completed',
      'completed',
      'completed', // INITIATING_PASSTHROUGH — implicitly completed, no DONE banner in this flow
      'completed',
    ]);
    expect(activeIdx).toBe(steps.length);
  });

  it('a red label does not travel with healthy progress after a transient error', () => {
    // Mid-run (before the terminal notification arrives): once healthy INFOs
    // resume after an error, the step must be active again — the incident
    // showed "Failed to write firmware" in red while writing at 15%.
    const step = flashingStep([
      ...buildPrelude,
      n(Err, FLASHING_FIRMWARE, BuildFirmwareSubstep.TargetMismatch),
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.WritingFirmware, 15),
    ]);
    expect(step.status).toBe('active');
    expect(step.currentSubstep).toBe(BuildFirmwareSubstep.WritingFirmware);
    expect(step.progress).toBe(15);
  });

  it('substep-less terminal ERROR does not inherit the last INFO substep', () => {
    // A genuine failure where only the strategy's bare terminal ERROR arrives:
    // the failure label must be generic, not "Failed to restart device"
    // borrowed from the last healthy INFO.
    const step = flashingStep([
      ...buildPrelude,
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.RestartingDevice),
      n(Err, FLASHING_FIRMWARE),
    ]);
    expect(step.status).toBe('error');
    expect(step.currentSubstep).toBeUndefined();
  });

  it('substep-less terminal ERROR keeps the substep a prior ERROR set', () => {
    // The parser attributes the failure (e.g. curl timeout → UploadingFirmware),
    // then the strategy emits its trailing bare terminal ERROR. The specific
    // label must survive.
    const step = flashingStep([
      ...buildPrelude,
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.UploadingFirmware, 48),
      n(Err, FLASHING_FIRMWARE, BuildFirmwareSubstep.UploadingFirmware),
      n(Err, FLASHING_FIRMWARE),
    ]);
    expect(step.status).toBe('error');
    expect(step.currentSubstep).toBe(BuildFirmwareSubstep.UploadingFirmware);
  });

  it('ERROR with explicit substep as last notification is shown', () => {
    const step = flashingStep([
      ...buildPrelude,
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.UploadingFirmware, 10),
      n(Err, FLASHING_FIRMWARE, BuildFirmwareSubstep.UploadingFirmware),
    ]);
    expect(step.status).toBe('error');
    expect(step.currentSubstep).toBe(BuildFirmwareSubstep.UploadingFirmware);
  });

  it('happy path completes every step', () => {
    const { steps, activeIdx } = reduceNotifications(
      [
        ...buildPrelude,
        n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.ConnectingToDevice),
        n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.WritingFirmware, 100),
        n(Success, FLASHING_FIRMWARE),
      ],
      BuildJobType.Flash,
      FlashingMethod.UART,
    );
    expect(steps.every((s) => s.status === 'completed')).toBe(true);
    expect(activeIdx).toBe(steps.length);
  });

  it('INFO progress is reflected on the active step', () => {
    const step = flashingStep([
      ...buildPrelude,
      n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.WritingFirmware, 42),
    ]);
    expect(step.status).toBe('active');
    expect(step.progress).toBe(42);
  });

  it('build-only jobs have three steps and no flashing step', () => {
    const { steps } = reduceNotifications(
      buildPrelude,
      BuildJobType.Build,
      FlashingMethod.UART,
    );
    expect(steps).toHaveLength(3);
    expect(steps.map((s) => s.step)).not.toContain(FLASHING_FIRMWARE);
  });

  describe('initiating passthrough step', () => {
    it('is included for passthrough methods on Flash jobs only', () => {
      for (const method of [
        FlashingMethod.BetaflightPassthrough,
        FlashingMethod.EdgeTxPassthrough,
        FlashingMethod.Passthrough,
      ]) {
        expect(highLevelStepsFor(BuildJobType.Flash, method)).toEqual([
          VERIFYING_BUILD_SYSTEM,
          DOWNLOADING_FIRMWARE,
          BUILDING_FIRMWARE,
          INITIATING_PASSTHROUGH,
          FLASHING_FIRMWARE,
        ]);
        expect(highLevelStepsFor(BuildJobType.Build, method)).toHaveLength(3);
      }
      for (const method of [FlashingMethod.UART, FlashingMethod.WIFI]) {
        expect(highLevelStepsFor(BuildJobType.Flash, method)).not.toContain(
          INITIATING_PASSTHROUGH,
        );
      }
    });

    it('completes on PASSTHROUGH DONE Success and stays completed while flashing runs', () => {
      // The recovery window: the completed "Passthrough done" step must remain
      // visible while esptool retries the connection.
      const { steps } = reduceNotifications(
        [
          ...buildPrelude,
          n(Info, INITIATING_PASSTHROUGH, BuildFirmwareSubstep.DetectingDevice),
          n(
            Info,
            INITIATING_PASSTHROUGH,
            BuildFirmwareSubstep.ConnectingToDevice,
          ),
          n(Success, INITIATING_PASSTHROUGH),
          n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.ConnectingToDevice),
        ],
        BuildJobType.Flash,
        FlashingMethod.BetaflightPassthrough,
      );
      const passthrough = steps.find((s) => s.step === INITIATING_PASSTHROUGH)!;
      const flashing = steps.find((s) => s.step === FLASHING_FIRMWARE)!;
      expect(passthrough.status).toBe('completed');
      expect(flashing.status).toBe('active');
      expect(flashing.currentSubstep).toBe(
        BuildFirmwareSubstep.ConnectingToDevice,
      );
    });

    it('is implicitly completed when flashing starts without a DONE banner', () => {
      // "Flash another" leaves the FC in passthrough mode — the flasher skips
      // straight to the upload without printing PASSTHROUGH DONE.
      const { steps } = reduceNotifications(
        [
          ...buildPrelude,
          n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.ConnectingToDevice),
        ],
        BuildJobType.Flash,
        FlashingMethod.BetaflightPassthrough,
      );
      const passthrough = steps.find((s) => s.step === INITIATING_PASSTHROUGH)!;
      expect(passthrough.status).toBe('completed');
    });

    it('a failed passthrough init does not paint the never-started flashing step red', () => {
      // ETX init timeout: the parser attributes the error to the passthrough
      // step, then the strategy emits its bare terminal ERROR on
      // FLASHING_FIRMWARE, which never started.
      const { steps, activeIdx } = reduceNotifications(
        [
          ...buildPrelude,
          n(
            Info,
            INITIATING_PASSTHROUGH,
            BuildFirmwareSubstep.ConnectingToDevice,
          ),
          n(
            Err,
            INITIATING_PASSTHROUGH,
            BuildFirmwareSubstep.ConnectingToDevice,
          ),
          n(Err, FLASHING_FIRMWARE),
        ],
        BuildJobType.Flash,
        FlashingMethod.EdgeTxPassthrough,
      );
      const passthrough = steps.find((s) => s.step === INITIATING_PASSTHROUGH)!;
      const flashing = steps.find((s) => s.step === FLASHING_FIRMWARE)!;
      expect(passthrough.status).toBe('error');
      expect(passthrough.currentSubstep).toBe(
        BuildFirmwareSubstep.ConnectingToDevice,
      );
      expect(flashing.status).toBe('pending');
      expect(activeIdx).toBe(steps.indexOf(passthrough));
    });

    it('recovery failure: DONE reached but the receiver never responds', () => {
      const { steps } = reduceNotifications(
        [
          ...buildPrelude,
          n(
            Info,
            INITIATING_PASSTHROUGH,
            BuildFirmwareSubstep.ConnectingToDevice,
          ),
          n(Success, INITIATING_PASSTHROUGH),
          n(Info, FLASHING_FIRMWARE, BuildFirmwareSubstep.ConnectingToDevice),
          n(Err, FLASHING_FIRMWARE, BuildFirmwareSubstep.ConnectingToDevice),
          n(Err, FLASHING_FIRMWARE),
        ],
        BuildJobType.Flash,
        FlashingMethod.BetaflightPassthrough,
      );
      const passthrough = steps.find((s) => s.step === INITIATING_PASSTHROUGH)!;
      const flashing = steps.find((s) => s.step === FLASHING_FIRMWARE)!;
      expect(passthrough.status).toBe('completed');
      expect(flashing.status).toBe('error');
      expect(flashing.currentSubstep).toBe(
        BuildFirmwareSubstep.ConnectingToDevice,
      );
    });
  });
});
