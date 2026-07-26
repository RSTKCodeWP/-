import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { NextIntlClientProvider } from "next-intl";

import messages from "../../../../locales/en.json";
import { CockpitTopBar } from "@/components/cockpit/CockpitTopBar";

/** The safety band reads live telemetry + arm state from real stores; their
 * defaults (disarmed, no telemetry) are enough — the band renders its stat
 * scaffold regardless of data, which is exactly the "always-on" contract. */
function renderBand(props: { lean?: boolean } = {}) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <CockpitTopBar {...props} />
    </NextIntlClientProvider>,
  );
}

describe("CockpitTopBar (always-on safety band)", () => {
  afterEach(cleanup);

  it("always renders the safety stats (arm pill + battery/GPS/link)", () => {
    const { container } = renderBand();
    expect(container.querySelector(".safety")).not.toBeNull();
    // Arm pill (disarmed by default) — the safety-critical readout.
    expect(screen.getByText(messages.cockpit.disarmed.toUpperCase())).toBeTruthy();
    // Battery / GPS / link stat labels are present.
    expect(screen.getByText(messages.cockpit.band.batt)).toBeTruthy();
    expect(screen.getByText(messages.cockpit.strip.gps)).toBeTruthy();
    expect(screen.getByText(messages.cockpit.strip.link)).toBeTruthy();
  });

  it("shows the decorative wordmark in the full band", () => {
    renderBand({ lean: false });
    expect(screen.getByText("ADOS")).toBeTruthy();
  });

  it("drops the wordmark in lean mode but keeps the safety stats", () => {
    const { container } = renderBand({ lean: true });
    expect(screen.queryByText("ADOS")).toBeNull();
    // Safety pill + stats stay — lean only removes the decorative label.
    expect(container.querySelector(".safety")).not.toBeNull();
    expect(screen.getByText(messages.cockpit.disarmed.toUpperCase())).toBeTruthy();
    expect(screen.getByText(messages.cockpit.strip.gps)).toBeTruthy();
  });
});
