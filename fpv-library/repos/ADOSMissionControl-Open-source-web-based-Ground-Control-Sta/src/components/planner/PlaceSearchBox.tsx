/**
 * @module PlaceSearchBox
 * @description Top-left map search box. Accepts a place name (forward-geocoded
 * via Nominatim, 1 req/s, cached) OR a raw coordinate pair (parsed locally, no
 * network) and pans the planner map to the result. Focused by the "/" shortcut.
 * @license GPL-3.0-only
 */
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Search, X, Loader2 } from "lucide-react";
import { usePlannerStore } from "@/stores/planner-store";
import { forwardGeocode, type ForwardGeocodeResult } from "@/lib/geocoding/forward";
import { parseLatLon } from "@/lib/geocoding/parse-latlon";
import { isDemoMode } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";

/** DOM event the keyboard owner fires to focus this box (the "/" shortcut). */
export const FOCUS_PLACE_SEARCH_EVENT = "plan:focus-place-search";

export function PlaceSearchBox() {
  const t = useTranslations("planner");
  const { toast } = useToast();
  const requestPan = usePlannerStore((s) => s.requestPan);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ForwardGeocodeResult[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const focus = () => inputRef.current?.focus();
    document.addEventListener(FOCUS_PLACE_SEARCH_EVENT, focus);
    return () => document.removeEventListener(FOCUS_PLACE_SEARCH_EVENT, focus);
  }, []);

  const panTo = useCallback(
    (lat: number, lon: number) => {
      requestPan(lat, lon);
      setResults([]);
    },
    [requestPan],
  );

  const submit = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    // A coordinate pair pans immediately with no network round-trip.
    const coord = parseLatLon(q);
    if (coord) {
      panTo(coord.lat, coord.lon);
      return;
    }
    // Demo mode never reaches the network — a place name can't be resolved.
    if (isDemoMode()) {
      toast(t("searchOfflineDemo"), "info");
      return;
    }
    setBusy(true);
    try {
      const found = await forwardGeocode(q, 5);
      if (found.length === 0) {
        setResults([]);
        toast(t("searchNoResults"), "info");
      } else if (found.length === 1) {
        panTo(found[0].lat, found[0].lon);
      } else {
        setResults(found);
      }
    } finally {
      setBusy(false);
    }
  }, [query, panTo, toast, t]);

  return (
    <div className="absolute top-3 left-3 z-[1000] w-64">
      <div className="flex items-center gap-2 px-2 py-1.5 bg-bg-secondary/90 backdrop-blur-sm border border-border-default rounded-lg">
        {busy ? (
          <Loader2 size={14} className="text-text-tertiary animate-spin shrink-0" />
        ) : (
          <Search size={14} className="text-text-tertiary shrink-0" />
        )}
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void submit();
            } else if (e.key === "Escape") {
              setResults([]);
              inputRef.current?.blur();
            }
          }}
          placeholder={t("searchPlaceholder")}
          aria-label={t("searchPlaceholder")}
          className="flex-1 min-w-0 bg-transparent text-xs text-text-primary placeholder:text-text-tertiary outline-none"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setResults([]);
            }}
            aria-label={t("searchClear")}
            className="text-text-tertiary hover:text-text-primary cursor-pointer shrink-0"
          >
            <X size={12} />
          </button>
        )}
      </div>
      {results.length > 0 && (
        <div className="mt-1 bg-bg-secondary/95 backdrop-blur-sm border border-border-default rounded-lg overflow-hidden">
          {results.map((r, i) => (
            <button
              key={`${r.lat},${r.lon}-${i}`}
              onClick={() => {
                panTo(r.lat, r.lon);
                setQuery(r.name);
              }}
              className="w-full text-left px-2 py-1.5 text-[11px] text-text-secondary hover:bg-bg-tertiary hover:text-text-primary cursor-pointer truncate"
            >
              {r.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
