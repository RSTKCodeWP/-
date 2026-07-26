import {
  BuildFirmwareStep,
  BuildFirmwareSubstep,
  BuildJobType,
  BuildProgressNotification,
  BuildProgressNotificationType,
  FlashingMethod,
} from '../../gql/generated/types';

export type StepStatus = 'pending' | 'active' | 'completed' | 'error';

export interface ReducedStep {
  step: BuildFirmwareStep;
  status: StepStatus;
  currentSubstep?: BuildFirmwareSubstep;
  progress?: number;
}

export interface ReducedState {
  steps: ReducedStep[];
  activeIdx: number;
}

export const PROGRESSIVE_MESSAGES = new Set<BuildFirmwareSubstep>([
  BuildFirmwareSubstep.WritingFirmware,
  BuildFirmwareSubstep.UploadingFirmware,
]);

const KNOWN_SUBSTEPS = new Set<string>(Object.values(BuildFirmwareSubstep));

function parseSubstep(
  value: string | null | undefined,
): BuildFirmwareSubstep | undefined {
  return value != null && KNOWN_SUBSTEPS.has(value)
    ? (value as BuildFirmwareSubstep)
    : undefined;
}

export function highLevelStepsFor(
  jobType: BuildJobType,
  flashingMethod?: FlashingMethod,
): BuildFirmwareStep[] {
  const isBuildOnly
    = jobType === BuildJobType.Build
      || flashingMethod === FlashingMethod.Stock_BL
      || flashingMethod === FlashingMethod.Zip;
  if (isBuildOnly) {
    return [
      BuildFirmwareStep.VERIFYING_BUILD_SYSTEM,
      BuildFirmwareStep.DOWNLOADING_FIRMWARE,
      BuildFirmwareStep.BUILDING_FIRMWARE,
    ];
  }
  const isPassthrough
    = flashingMethod === FlashingMethod.BetaflightPassthrough
      || flashingMethod === FlashingMethod.EdgeTxPassthrough
      || flashingMethod === FlashingMethod.Passthrough;
  return [
    BuildFirmwareStep.VERIFYING_BUILD_SYSTEM,
    BuildFirmwareStep.DOWNLOADING_FIRMWARE,
    BuildFirmwareStep.BUILDING_FIRMWARE,
    ...(isPassthrough ? [BuildFirmwareStep.INITIATING_PASSTHROUGH] : []),
    BuildFirmwareStep.FLASHING_FIRMWARE,
  ];
}

// Notifications are applied in order and the last state wins. This is safe
// because both flashing strategies always emit the terminal SUCCESS/ERROR for
// the final step after all parser output. In particular:
// - a SUCCESS clears a transient earlier error on the same step (a flash that
//   recovered and completed must end green);
// - a later INFO returns an errored step to 'active', so a red label cannot
//   "travel" along with healthy progress output;
// - an ERROR without a substep keeps an existing label only if a prior ERROR
//   set it (the strategies' trailing terminal ERROR carries no substep and
//   must not downgrade the parser's specific failure label) — it never
//   inherits a substep from healthy INFO progress.
export function reduceNotifications(
  notifications: BuildProgressNotification[],
  jobType: BuildJobType,
  flashingMethod: FlashingMethod | undefined,
): ReducedState {
  const stepOrder = highLevelStepsFor(jobType, flashingMethod);
  const byStep = new Map<BuildFirmwareStep, ReducedStep>();
  for (const step of stepOrder) {
    byStep.set(step, { step, status: 'pending' });
  }

  // Track which steps have received any notification (in order of first arrival).
  const seen: BuildFirmwareStep[] = [];
  for (const n of notifications) {
    if (!n.step) continue;
    const target = byStep.get(n.step);
    if (!target) continue;
    if (!seen.includes(n.step)) {
      seen.push(n.step);
    }
    const substep = parseSubstep(n.substep);
    if (n.type === BuildProgressNotificationType.Error) {
      // The strategies emit a substep-less terminal ERROR on the final step
      // even when the failure happened in an earlier step (e.g. passthrough
      // init never completed, so FLASHING_FIRMWARE never started). Don't
      // paint a never-started step red when the failure is already
      // attributed upstream.
      if (
        substep === undefined
        && target.status === 'pending'
        && stepOrder
          .slice(0, stepOrder.indexOf(n.step))
          .some((s) => byStep.get(s)!.status === 'error')
      ) {
        continue;
      }
      const wasAlreadyError = target.status === 'error';
      target.status = 'error';
      target.currentSubstep
        = substep ?? (wasAlreadyError ? target.currentSubstep : undefined);
      if (n.progress != null) target.progress = n.progress;
      continue;
    }
    if (n.type === BuildProgressNotificationType.Success) {
      target.status = 'completed';
      if (substep != null) target.currentSubstep = substep;
      if (n.progress != null) target.progress = n.progress;
      continue;
    }
    // Info: mark this step active (also recovers from a transient error).
    if (target.status !== 'completed') {
      target.status = 'active';
    }
    if (substep != null) target.currentSubstep = substep;
    if (n.progress != null) target.progress = n.progress;
  }

  // Any step before the latest-seen that's still 'active' or 'pending' is
  // implicitly complete (we've moved past it). 'pending' matters for
  // INITIATING_PASSTHROUGH, which is fed only by parser regexes and must not
  // sit as an unchecked circle above an active step if the flasher output
  // ever changes. Errors remain errors.
  const lastSeen = seen[seen.length - 1];
  if (lastSeen) {
    const lastIdx = stepOrder.indexOf(lastSeen);
    for (let i = 0; i < lastIdx; i += 1) {
      const step = byStep.get(stepOrder[i])!;
      if (step.status === 'active' || step.status === 'pending') {
        step.status = 'completed';
      }
    }
  }

  const reducedSteps = stepOrder.map((s) => byStep.get(s)!);
  let activeIdx = reducedSteps.findIndex(
    (s) => s.status === 'active' || s.status === 'error',
  );
  if (activeIdx === -1) {
    const firstPending = reducedSteps.findIndex((s) => s.status === 'pending');
    activeIdx = firstPending === -1 ? reducedSteps.length : firstPending;
  }
  return { steps: reducedSteps, activeIdx };
}
