// Physical UI surfaces: OLED screens, button mappings, menu screens, plus the factory-reset call.

import type {
  FactoryResetResult,
  OledUpdate,
  ScreensUpdate,
  UiConfig,
} from "./types";
import { gsRequest, type RequestContext } from "./request";

export function getUi(ctx: RequestContext): Promise<UiConfig> {
  return gsRequest<UiConfig>(ctx, "/api/v1/ground-station/ui");
}

export function setOled(ctx: RequestContext, update: OledUpdate): Promise<UiConfig> {
  return gsRequest<UiConfig>(ctx, "/api/v1/ground-station/ui/oled", {
    method: "PUT",
    body: JSON.stringify(update),
  });
}

export function setButtons(
  ctx: RequestContext,
  mapping: Record<string, unknown>,
): Promise<UiConfig> {
  return gsRequest<UiConfig>(ctx, "/api/v1/ground-station/ui/buttons", {
    method: "PUT",
    body: JSON.stringify(mapping),
  });
}

export function setScreens(ctx: RequestContext, update: ScreensUpdate): Promise<UiConfig> {
  return gsRequest<UiConfig>(ctx, "/api/v1/ground-station/ui/screens", {
    method: "PUT",
    body: JSON.stringify(update),
  });
}

export function factoryReset(
  ctx: RequestContext,
  confirmToken: string,
): Promise<FactoryResetResult> {
  const q = encodeURIComponent(confirmToken);
  return gsRequest<FactoryResetResult>(
    ctx,
    `/api/v1/ground-station/factory-reset?confirm=${q}`,
    { method: "POST" },
  );
}
