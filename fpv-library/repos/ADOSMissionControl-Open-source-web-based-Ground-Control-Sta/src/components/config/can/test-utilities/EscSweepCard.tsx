"use client";

/**
 * @module EscSweepCard
 * @description ESC RawCommand sweep UI. Walks the selected channel from
 * `pwmFrom` to `pwmTo` in `step`-µs increments, holding each value for
 * `dwell` seconds and re-emitting an `esc.RawCommand` broadcast at a
 * fixed 50 Hz throughout the dwell window. Other channels are padded
 * with zero so the bench fixture stays still.
 *
 * Execution is gated behind a red-variant confirm dialog because the
 * broadcast drives motor output directly.
 *
 * @license GPL-3.0-only
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Square, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";

/** Outbound rate while a sweep is in flight. */
const SEND_INTERVAL_MS = 20; // 50 Hz
/** Total channels in the broadcast array. */
const CHANNEL_COUNT = 8;
/** Inclusive PWM bounds. */
const PWM_MIN = 1000;
const PWM_MAX = 2000;

/** Map a 1000..2000 µs PWM to the int14 throttle range expected by ESCs. */
function pwmToCmd(pwm: number): number {
  const clamped = Math.max(PWM_MIN, Math.min(PWM_MAX, pwm));
  const normalized = (clamped - PWM_MIN) / (PWM_MAX - PWM_MIN);
  return Math.round(normalized * 8191);
}

export interface EscSweepClient {
  sendEscRawCommand(cmd: number[]): Promise<void>;
}

export interface EscSweepCardProps {
  client?: EscSweepClient | null;
}

export function EscSweepCard({ client }: EscSweepCardProps = {}) {
  const t = useTranslations("canConfig.testUtilities.escSweep");

  const [channel, setChannel] = useState("0");
  const [pwmFrom, setPwmFrom] = useState("1000");
  const [pwmTo, setPwmTo] = useState("2000");
  const [step, setStep] = useState("50");
  const [dwell, setDwell] = useState("1");

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [currentPwm, setCurrentPwm] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stopRef = useRef(false);
  const runIdRef = useRef(0);

  const stop = useCallback(() => {
    stopRef.current = true;
  }, []);

  useEffect(() => stop, [stop]);

  const runSweep = useCallback(async () => {
    setConfirmOpen(false);
    setError(null);
    if (!client) {
      setError(t("pendingMessage"));
      return;
    }
    const ch = Math.max(0, Math.min(CHANNEL_COUNT - 1, Number(channel) | 0));
    const from = Math.max(PWM_MIN, Math.min(PWM_MAX, Number(pwmFrom) | 0));
    const to = Math.max(PWM_MIN, Math.min(PWM_MAX, Number(pwmTo) | 0));
    const stepValue = Math.max(1, Number(step) | 0);
    const dwellMs = Math.max(1, Number(dwell) | 0) * 1000;
    const direction = to >= from ? 1 : -1;

    runIdRef.current += 1;
    const myRun = runIdRef.current;
    stopRef.current = false;
    setRunning(true);
    try {
      for (
        let pwm = from;
        direction > 0 ? pwm <= to : pwm >= to;
        pwm += direction * stepValue
      ) {
        if (stopRef.current || runIdRef.current !== myRun) break;
        setCurrentPwm(pwm);
        const cmd = new Array(CHANNEL_COUNT).fill(0);
        cmd[ch] = pwmToCmd(pwm);
        const dwellEnd = Date.now() + dwellMs;
        while (Date.now() < dwellEnd) {
          if (stopRef.current || runIdRef.current !== myRun) break;
          try {
            await client.sendEscRawCommand(cmd);
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
            stopRef.current = true;
            break;
          }
          await new Promise((r) => setTimeout(r, SEND_INTERVAL_MS));
        }
      }
      // Always send a zero command at the end to release the motor.
      if (client) {
        try {
          await client.sendEscRawCommand(new Array(CHANNEL_COUNT).fill(0));
        } catch {
          // best-effort safety stop; don't overwrite the displayed error
        }
      }
    } finally {
      setRunning(false);
      setCurrentPwm(null);
    }
  }, [client, channel, pwmFrom, pwmTo, step, dwell, t]);

  return (
    <>
      <Card title={t("title")}>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <Input
            label={t("channel")}
            type="number"
            min={0}
            max={CHANNEL_COUNT - 1}
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            disabled={running}
          />
          <Input
            label={t("pwmFrom")}
            type="number"
            min={PWM_MIN}
            max={PWM_MAX}
            value={pwmFrom}
            onChange={(e) => setPwmFrom(e.target.value)}
            unit="µs"
            disabled={running}
          />
          <Input
            label={t("pwmTo")}
            type="number"
            min={PWM_MIN}
            max={PWM_MAX}
            value={pwmTo}
            onChange={(e) => setPwmTo(e.target.value)}
            unit="µs"
            disabled={running}
          />
          <Input
            label={t("step")}
            type="number"
            min={1}
            value={step}
            onChange={(e) => setStep(e.target.value)}
            unit="µs"
            disabled={running}
          />
          <Input
            label={t("dwell")}
            type="number"
            min={1}
            value={dwell}
            onChange={(e) => setDwell(e.target.value)}
            unit="s"
            disabled={running}
          />
        </div>
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          {running ? (
            <Button
              variant="danger"
              size="sm"
              icon={<Square size={12} />}
              onClick={stop}
              data-testid="esc-sweep-stop"
            >
              {t("stop")}
            </Button>
          ) : (
            <Button
              variant="danger"
              size="sm"
              icon={<Zap size={12} />}
              onClick={() => setConfirmOpen(true)}
              disabled={!client}
              data-testid="esc-sweep-trigger"
            >
              {t("button")}
            </Button>
          )}
          {currentPwm !== null && (
            <span
              className="text-[11px] text-status-warning font-mono"
              data-testid="esc-sweep-current"
            >
              {t("currentPwm", { pwm: currentPwm })}
            </span>
          )}
          {error && (
            <span
              className="text-[11px] text-status-error"
              data-testid="esc-sweep-error"
            >
              {error}
            </span>
          )}
        </div>
      </Card>

      <ConfirmDialog
        open={confirmOpen}
        onConfirm={runSweep}
        onCancel={() => setConfirmOpen(false)}
        title={t("safetyTitle")}
        message={t("safetyMessage")}
        confirmLabel={t("safetyConfirm")}
        variant="danger"
      />
    </>
  );
}
