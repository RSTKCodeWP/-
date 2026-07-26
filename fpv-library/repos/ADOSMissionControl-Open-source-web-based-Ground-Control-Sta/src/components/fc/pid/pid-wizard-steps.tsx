import { Upload, BarChart3, Sparkles, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { WizardStep } from "@/lib/analysis/types";

export const STEPS: { id: WizardStep; label: string; icon: typeof Upload }[] = [
  { id: "upload", label: "Upload", icon: Upload },
  { id: "analysis", label: "Analysis", icon: BarChart3 },
  { id: "recommendations", label: "AI Recs", icon: Sparkles },
  { id: "apply", label: "Apply", icon: CheckCircle },
];

export type AnalysisTab = "fft" | "step" | "tracking" | "motors" | "summary";

export const ANALYSIS_TABS: { id: AnalysisTab; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "fft", label: "Noise (FFT)" },
  { id: "step", label: "Step Response" },
  { id: "tracking", label: "Tracking" },
  { id: "motors", label: "Motors" },
];

interface StepIndicatorProps {
  wizardStep: WizardStep;
  setWizardStep: (step: WizardStep) => void;
}

export function StepIndicator({ wizardStep, setWizardStep }: StepIndicatorProps) {
  const stepIndex = STEPS.findIndex((s) => s.id === wizardStep);
  return (
    <div className="flex items-center justify-center gap-0">
      {STEPS.map((step, i) => {
        const isCompleted = i < stepIndex;
        const isCurrent = i === stepIndex;
        const Icon = step.icon;
        return (
          <div key={step.id} className="flex items-center">
            <button
              onClick={() => { if (isCompleted || isCurrent) setWizardStep(step.id); }}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium transition-colors cursor-pointer",
                isCompleted && "text-status-success",
                isCurrent && "text-accent-primary",
                !isCompleted && !isCurrent && "text-text-tertiary",
              )}
            >
              <div className={cn(
                "w-5 h-5 flex items-center justify-center border transition-colors",
                isCompleted && "border-status-success bg-status-success/10",
                isCurrent && "border-accent-primary bg-accent-primary/10",
                !isCompleted && !isCurrent && "border-border-default",
              )}>
                {isCompleted ? <CheckCircle size={10} className="text-status-success" /> : <Icon size={10} />}
              </div>
              <span className="hidden sm:inline">{step.label}</span>
            </button>
            {i < STEPS.length - 1 && (
              <div className={cn("w-8 h-px", i < stepIndex ? "bg-status-success" : "bg-border-default")} />
            )}
          </div>
        );
      })}
    </div>
  );
}
