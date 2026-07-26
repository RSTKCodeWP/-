/**
 * @module WeatherCard
 * @description Planner Review-band card giving a flight go / caution / no-go
 * judgment from live wind. It fetches current wind + winds-aloft + a short gust
 * forecast once (debounced, aborted on coord change) from the free, keyless
 * Open-Meteo API and grades it with the pure `assessWeather` thresholds. In
 * demo mode it never touches the network: it shows a clearly-labelled mock
 * report instead of a fabricated live reading. Unknown fields render as "—".
 * @license GPL-3.0-only
 */
"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Wind,
  Gauge,
  Thermometer,
  Navigation,
  Mountain,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import { cn, isDemoMode } from "@/lib/utils";
import { fetchWeather, type WeatherReport } from "@/lib/weather/open-meteo";
import {
  assessWeather,
  type GoNoGoLevel,
  type WeatherReasonCode,
} from "@/lib/weather/go-no-go";

interface WeatherCardProps {
  /** Latitude in decimal degrees (WGS84). */
  lat: number;
  /** Longitude in decimal degrees (WGS84). */
  lon: number;
  className?: string;
}

/** Deterministic mock shown in demo mode — never a live reading. */
const DEMO_REPORT: WeatherReport = {
  time: null,
  windSpeedMps: 4.2,
  windGustMps: 6.4,
  windDirectionDeg: 285,
  temperatureC: 24,
  levels: [
    { heightM: 80, speedMps: 5.6, directionDeg: 288 },
    { heightM: 120, speedMps: 6.9, directionDeg: 292 },
    { heightM: 180, speedMps: 8.3, directionDeg: 296 },
  ],
  forecastPeakGustMps: 7.1,
  forecastWindowHours: 6,
};

const LEVEL_STYLE: Record<
  GoNoGoLevel,
  { badge: string; Icon: LucideIcon; labelKey: string }
> = {
  go: { badge: "bg-status-success/15 text-status-success", Icon: CheckCircle2, labelKey: "weather.go" },
  caution: { badge: "bg-status-warning/15 text-status-warning", Icon: AlertTriangle, labelKey: "weather.caution" },
  nogo: { badge: "bg-status-error/15 text-status-error", Icon: XCircle, labelKey: "weather.nogo" },
};

const REASON_KEY: Record<WeatherReasonCode, string> = {
  windCaution: "weather.reasonWindCaution",
  windNogo: "weather.reasonWindNogo",
  gustCaution: "weather.reasonGustCaution",
  gustNogo: "weather.reasonGustNogo",
  noData: "weather.reasonNoData",
};

const COMPASS = [
  "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
] as const;

/** 16-point compass abbreviation for a direction the wind blows FROM. */
function compass(deg: number): string {
  const i = Math.round((((deg % 360) + 360) % 360) / 22.5) % 16;
  return COMPASS[i];
}

/** Format a speed in m/s to one decimal, or "—" when unknown. */
function fmtSpeed(v: number | null): string {
  return v === null ? "—" : v.toFixed(1);
}

/** Format a direction as "285° WNW", or "—" when unknown. */
function fmtDir(deg: number | null): string {
  return deg === null ? "—" : `${Math.round(deg)}° ${compass(deg)}`;
}

/** Format a temperature in °C to a whole degree, or "—" when unknown. */
function fmtTemp(v: number | null): string {
  return v === null ? "—" : `${Math.round(v)}°`;
}

export function WeatherCard({ lat, lon, className }: WeatherCardProps) {
  const t = useTranslations("planner");
  const demo = useMemo(() => isDemoMode(), []);
  const [report, setReport] = useState<WeatherReport | null>(demo ? DEMO_REPORT : null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  // Round to ~100 m so a map pan does not trigger a fetch per pixel.
  const rLat = Math.round(lat * 1000) / 1000;
  const rLon = Math.round(lon * 1000) / 1000;

  useEffect(() => {
    // Demo mode is offline by contract: the initial state already holds the
    // labelled mock, so there is nothing to fetch and no state to touch.
    if (demo) return;

    const controller = new AbortController();
    let active = true;

    // Debounce so a map pan does not fire a request per intermediate coord.
    // All state updates live inside callbacks (never synchronously in the
    // effect body) so a coord change can't trigger a cascading render.
    const timer = setTimeout(() => {
      if (!active) return;
      if (!Number.isFinite(rLat) || !Number.isFinite(rLon)) {
        setReport(null);
        setLoading(false);
        setError(false);
        return;
      }
      setLoading(true);
      setError(false);
      fetchWeather(rLat, rLon, controller.signal)
        .then((r) => {
          if (!active) return;
          if (r) {
            setReport(r);
            setError(false);
          } else {
            setReport(null);
            setError(true);
          }
        })
        .catch(() => {
          if (active) {
            setReport(null);
            setError(true);
          }
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 500);

    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [demo, rLat, rLon]);

  const assessment = useMemo(
    () => (report ? assessWeather(report) : null),
    [report],
  );

  const surfaceRows: { key: string; label: string; icon: LucideIcon; value: string }[] =
    report
      ? [
          { key: "wind", label: t("weather.wind"), icon: Wind, value: `${fmtSpeed(report.windSpeedMps)} m/s` },
          { key: "gust", label: t("weather.gust"), icon: Gauge, value: `${fmtSpeed(report.windGustMps)} m/s` },
          { key: "dir", label: t("weather.direction"), icon: Navigation, value: fmtDir(report.windDirectionDeg) },
          { key: "temp", label: t("weather.temp"), icon: Thermometer, value: fmtTemp(report.temperatureC) },
        ]
      : [];

  const style = assessment ? LEVEL_STYLE[assessment.level] : null;
  const BadgeIcon = style?.Icon ?? Wind;

  return (
    <div
      className={cn(
        "bg-bg-secondary border border-border-default rounded-md p-3 text-xs",
        className,
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        <Wind className="w-3.5 h-3.5 text-accent-primary" />
        <span className="font-medium text-text-primary">{t("weather.title")}</span>
        {style && (
          <span
            className={cn(
              "ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
              style.badge,
            )}
          >
            <BadgeIcon className="w-3 h-3" />
            {t(style.labelKey)}
          </span>
        )}
      </div>

      {demo && (
        <div className="mb-2 text-[10px] text-status-warning">{t("weather.demoNote")}</div>
      )}

      {loading && !report ? (
        <div className="flex items-center gap-2 text-text-secondary">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          {t("weather.loading")}
        </div>
      ) : error && !report ? (
        <div className="text-text-secondary">{t("weather.error")}</div>
      ) : report ? (
        <div className="flex flex-col gap-2">
          {assessment && assessment.reasons.length > 0 && (
            <div className="text-[10px] text-text-tertiary">
              {assessment.reasons.map((r) => t(REASON_KEY[r])).join(" · ")}
            </div>
          )}

          <div className="grid grid-cols-1 gap-1.5">
            {surfaceRows.map((r) => {
              const Icon = r.icon;
              return (
                <div key={r.key} className="flex items-center gap-2">
                  <Icon className="w-3.5 h-3.5 text-text-secondary shrink-0" />
                  <span className="text-text-secondary">{r.label}</span>
                  <span className="ml-auto font-mono text-text-primary tabular-nums">{r.value}</span>
                </div>
              );
            })}
          </div>

          {report.levels.length > 0 && (
            <div className="pt-1.5 border-t border-border-default">
              <div className="flex items-center gap-2 mb-1 text-text-tertiary">
                <Mountain className="w-3 h-3 shrink-0" />
                <span>{t("weather.aloft")}</span>
              </div>
              <div className="grid grid-cols-1 gap-1">
                {report.levels.map((l) => (
                  <div key={l.heightM} className="flex items-center gap-2">
                    <span className="font-mono text-text-secondary tabular-nums w-10 shrink-0">
                      {l.heightM}m
                    </span>
                    <span className="font-mono text-text-primary tabular-nums">
                      {fmtSpeed(l.speedMps)} m/s
                    </span>
                    <span className="ml-auto text-text-tertiary">{fmtDir(l.directionDeg)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.forecastPeakGustMps !== null && report.forecastWindowHours !== null && (
            <div className="flex items-center gap-2 pt-1.5 border-t border-border-default">
              <Gauge className="w-3.5 h-3.5 text-text-secondary shrink-0" />
              <span className="text-text-secondary">
                {t("weather.forecastGust", { hours: report.forecastWindowHours })}
              </span>
              <span className="ml-auto font-mono text-text-primary tabular-nums">
                {fmtSpeed(report.forecastPeakGustMps)} m/s
              </span>
            </div>
          )}
        </div>
      ) : (
        <div className="text-text-secondary">{fmtSpeed(null)}</div>
      )}
    </div>
  );
}
