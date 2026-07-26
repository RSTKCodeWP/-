/**
 * @module SunTimesCard
 * @description Compact planner card showing today's sunrise / sunset / solar
 * noon and the two golden-hour windows for a given lat/lon, with a live
 * "golden hour now" badge. Pure display over `@/lib/sun-times`; the clock
 * ticks each minute so the badge stays current without a network call.
 * @license GPL-3.0-only
 */
"use client";

import { useEffect, useMemo, useState } from "react";
import { Sunrise, Sunset, Sun, Clock, Camera } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { sunTimesFor, isGoldenHour, type SunTimes } from "@/lib/sun-times";

interface SunTimesCardProps {
  /** Latitude in decimal degrees (WGS84). */
  lat: number;
  /** Longitude in decimal degrees (WGS84). */
  lon: number;
  /** Fixed instant to evaluate; omit to follow the live clock. */
  date?: Date;
  className?: string;
}

/** Local HH:MM, or an em-space placeholder for polar-day invalid dates. */
function fmtTime(d: Date | undefined): string {
  if (!d || Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** "HH:MM–HH:MM" range for a golden-hour window. */
function fmtRange(a: Date | undefined, b: Date | undefined): string {
  return `${fmtTime(a)}–${fmtTime(b)}`;
}

export function SunTimesCard({ lat, lon, date, className }: SunTimesCardProps) {
  const t = useTranslations("planner");
  // Live clock, null until mounted so SSR and the first client render agree.
  // When a fixed `date` is supplied it wins reactively and the clock stays off.
  // Timer callbacks own every state update, so nothing sets state synchronously
  // inside the effect body.
  const [liveNow, setLiveNow] = useState<Date | null>(null);

  useEffect(() => {
    if (date) return;
    let interval: ReturnType<typeof setInterval> | undefined;
    const first = setTimeout(() => {
      setLiveNow(new Date());
      interval = setInterval(() => setLiveNow(new Date()), 60_000);
    }, 0);
    return () => {
      clearTimeout(first);
      if (interval) clearInterval(interval);
    };
  }, [date]);

  const now = date ?? liveNow;

  const times = useMemo<SunTimes | null>(
    () => (now ? sunTimesFor(now, lat, lon) : null),
    [now, lat, lon],
  );
  const golden = useMemo(
    () => (now ? isGoldenHour(now, lat, lon) : false),
    [now, lat, lon],
  );

  const rows: { key: string; label: string; icon: typeof Sun; value: string }[] =
    times
      ? [
          { key: "sunrise", label: t("sunrise"), icon: Sunrise, value: fmtTime(times.sunrise) },
          { key: "solarNoon", label: t("solarNoon"), icon: Clock, value: fmtTime(times.solarNoon) },
          { key: "sunset", label: t("sunset"), icon: Sunset, value: fmtTime(times.sunset) },
          {
            key: "goldenAm",
            label: t("goldenHourMorning"),
            icon: Camera,
            value: fmtRange(times.sunrise, times.goldenHourEnd),
          },
          {
            key: "goldenPm",
            label: t("goldenHourEvening"),
            icon: Camera,
            value: fmtRange(times.goldenHourStart, times.sunset),
          },
        ]
      : [];

  return (
    <div
      className={cn(
        "bg-bg-secondary border border-border-default rounded-md p-3 text-xs",
        className,
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        <Sun className="w-3.5 h-3.5 text-accent-primary" />
        <span className="font-medium text-text-primary">{t("sunTimes")}</span>
        {golden && (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-accent-primary/15 px-2 py-0.5 text-[10px] font-medium text-accent-primary">
            <Camera className="w-3 h-3" />
            {t("goldenHourNow")}
          </span>
        )}
      </div>

      {rows.length === 0 ? (
        <div className="text-text-secondary">{fmtTime(undefined)}</div>
      ) : (
        <div className="grid grid-cols-1 gap-1.5">
          {rows.map((r) => {
            const Icon = r.icon;
            return (
              <div key={r.key} className="flex items-center gap-2">
                <Icon className="w-3.5 h-3.5 text-text-secondary shrink-0" />
                <span className="text-text-secondary">{r.label}</span>
                <span className="ml-auto font-mono text-text-primary tabular-nums">
                  {r.value}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
