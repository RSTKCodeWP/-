import { FunctionComponent, memo, ReactElement, useMemo } from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  CircularProgress,
  LinearProgress,
  Step,
  StepContent,
  StepIconProps,
  StepLabel,
  Stepper,
  Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { SxProps, Theme } from '@mui/system';
import { Trans, useTranslation } from 'react-i18next';
import {
  BuildFirmwareErrorType,
  BuildFlashFirmwareResult,
  BuildJobType,
  BuildProgressNotification,
  FlashingMethod,
} from '../../gql/generated/types';
import DocumentationLink from '../DocumentationLink';
import {
  PROGRESSIVE_MESSAGES,
  ReducedStep,
  reduceNotifications,
  StepStatus,
} from './reduceNotifications';

const StepIcon = ({
  status,
}: {
  status: StepStatus;
}): ReactElement => {
  switch (status) {
    case 'completed':
      return <CheckCircleIcon color="success" fontSize="medium" />;
    case 'error':
      return <ErrorIcon color="error" fontSize="medium" />;
    case 'active':
      return <CircularProgress size={20} />;
    case 'pending':
    default:
      return <RadioButtonUncheckedIcon color="disabled" fontSize="medium" />;
  }
};

const CustomStepIcon = (props: StepIconProps & { status: StepStatus }) => {
  return <StepIcon status={props.status} />;
};

const styles: Record<string, SxProps<Theme>> = {
  stepper: {
    marginTop: 1,
    marginBottom: 2,
  },
  subline: {
    marginTop: 0.5,
    marginBottom: 0.5,
  },
  progressBar: {
    height: 6,
    borderRadius: 3,
    marginTop: 0.5,
  },
  doneHint: {
    marginTop: 1,
    fontStyle: 'italic',
  },
  resultBlock: {
    marginTop: 1,
  },
  resultAlert: {
    marginTop: 1,
    marginBottom: 1,
  },
  errorMessage: {
    marginTop: 1,
    marginBottom: 1,
    a: {
      color: (theme: Theme) => theme.palette.custom.alertError.text,
    },
  },
};

type ErrorTitleKey =
  | 'BuildResponse.Error'
  | 'BuildResponse.GitDependencyError'
  | 'BuildResponse.PythonDependencyError'
  | 'BuildResponse.PlatformioDependencyError'
  | 'BuildResponse.BuildError'
  | 'BuildResponse.FlashError'
  | 'BuildResponse.TargetMismatch';

function errorTypeTitleKey(
  errorType: BuildFirmwareErrorType | null | undefined,
): ErrorTitleKey {
  switch (errorType) {
    case BuildFirmwareErrorType.GitDependencyError:
      return 'BuildResponse.GitDependencyError';
    case BuildFirmwareErrorType.PythonDependencyError:
      return 'BuildResponse.PythonDependencyError';
    case BuildFirmwareErrorType.PlatformioDependencyError:
      return 'BuildResponse.PlatformioDependencyError';
    case BuildFirmwareErrorType.BuildError:
      return 'BuildResponse.BuildError';
    case BuildFirmwareErrorType.FlashError:
      return 'BuildResponse.FlashError';
    case BuildFirmwareErrorType.TargetMismatch:
      return 'BuildResponse.TargetMismatch';
    case BuildFirmwareErrorType.GenericError:
    default:
      return 'BuildResponse.Error';
  }
}

interface FlashingStepperProps {
  notifications: BuildProgressNotification[];
  jobType: BuildJobType;
  flashingMethod?: FlashingMethod;
  hasLuaScript?: boolean;
  response?: BuildFlashFirmwareResult;
}

const FlashingStepper: FunctionComponent<FlashingStepperProps> = memo(
  ({ notifications, jobType, flashingMethod, hasLuaScript, response }) => {
    const { t } = useTranslation();

    const { steps, activeIdx } = useMemo(
      () => reduceNotifications(notifications, jobType, flashingMethod),
      [notifications, jobType, flashingMethod],
    );

    const isBuildOnly
      = jobType === BuildJobType.Build
        || flashingMethod === FlashingMethod.Stock_BL
        || flashingMethod === FlashingMethod.Zip;

    const sublineFor = (s: ReducedStep): ReactElement | null => {
      if (s.status !== 'active' && s.status !== 'error') return null;
      const isError = s.status === 'error';
      let text: string | null = null;
      if (isError) {
        text = s.currentSubstep
          ? t(`FlashingStepper.Failed.${s.currentSubstep}`, {
              defaultValue: t('FlashingStepper.Failed.Generic'),
            })
          : t('FlashingStepper.Failed.Generic');
      } else if (s.currentSubstep) {
        text = t(`FlashingStepper.Status.${s.currentSubstep}`);
      }
      const showProgress
        = !isError
          && s.progress != null
          && s.currentSubstep != null
          && PROGRESSIVE_MESSAGES.has(s.currentSubstep);
      let suffix = '';
      if (showProgress) {
        suffix = ` ${Math.round(s.progress!)}%`;
      } else if (!isError) {
        suffix = ' …';
      }

      return (
        <Box>
          {text && (
            <Typography
              variant="body2"
              color={isError ? 'error' : 'text.secondary'}
              sx={styles.subline}
            >
              {text}
              {suffix}
            </Typography>
          )}
          {showProgress && (
            <LinearProgress
              variant="determinate"
              value={Math.max(0, Math.min(100, s.progress!))}
              sx={styles.progressBar}
            />
          )}
        </Box>
      );
    };

    const renderResultBlock = (): ReactElement | null => {
      if (!response) return null;
      if (response.success) {
        return (
          <Box sx={styles.resultBlock}>
            {jobType === BuildJobType.Flash
              && flashingMethod === FlashingMethod.WIFI && (
              <Alert severity="warning" sx={styles.resultAlert}>
                <AlertTitle>{t('ConfiguratorView.Warning')}</AlertTitle>
                {t('ConfiguratorView.WaitForLEDBeforeDisconnectingPower')}
              </Alert>
            )}
            {hasLuaScript && (
              <Alert severity="info" sx={styles.resultAlert}>
                <AlertTitle>{t('ConfiguratorView.UpdateLuaScript')}</AlertTitle>
                {t('ConfiguratorView.UpdateLuaScriptOnRadio')}
              </Alert>
            )}
            {jobType === BuildJobType.Build && (
              <Alert severity="info" sx={styles.resultAlert}>
                <AlertTitle>{t('ConfiguratorView.BuildNotice')}</AlertTitle>
                {t('ConfiguratorView.FirmwareOpenedInFileExplorer')}
              </Alert>
            )}
            {isBuildOnly && (
              <Typography
                variant="body2"
                color="success.main"
                sx={styles.doneHint}
              >
                {flashingMethod === FlashingMethod.Stock_BL
                  ? t('FlashingStepper.StockBlDoneHint')
                  : t('FlashingStepper.BuildOnlyDoneHint')}
              </Typography>
            )}
          </Box>
        );
      }
      const errorType = response.errorType ?? BuildFirmwareErrorType.GenericError;
      return (
        <Box sx={styles.resultBlock}>
          <Alert severity="error" sx={styles.errorMessage}>
            <AlertTitle>{t(errorTypeTitleKey(errorType))}</AlertTitle>
            <p>
              <Trans
                i18nKey="BuildResponse.ErrorDetails"
                components={{
                  ExpresslrsLink: (
                    <DocumentationLink url="https://www.expresslrs.org/" />
                  ),
                  FlashingGuideLink: (
                    <DocumentationLink url="https://www.expresslrs.org/quick-start/getting-started/" />
                  ),
                  TroubleshootingGuideLink: (
                    <DocumentationLink url="https://www.expresslrs.org/quick-start/troubleshooting/#flashingupdating" />
                  ),
                  ExpressLRSDiscordLink: (
                    <DocumentationLink url="https://discord.gg/dS6ReFY" />
                  ),
                }}
              />
            </p>
          </Alert>
        </Box>
      );
    };

    return (
      <Box>
        <Stepper
          orientation="vertical"
          activeStep={Math.min(activeIdx, steps.length)}
          sx={styles.stepper}
        >
          {steps.map((s) => (
            <Step
              key={s.step}
              completed={s.status === 'completed'}
              active={s.status === 'active' || s.status === 'error'}
            >
              <StepLabel
                StepIconComponent={(p) => (
                  <CustomStepIcon {...p} status={s.status} />
                )}
                error={s.status === 'error'}
              >
                {t(`FlashingStepper.Step.${s.step}_${s.status}`, {
                  defaultValue: t(`FlashingStepper.Step.${s.step}`),
                })}
              </StepLabel>
              <StepContent>{sublineFor(s)}</StepContent>
            </Step>
          ))}
        </Stepper>
        {renderResultBlock()}
      </Box>
    );
  },
);

export default FlashingStepper;
