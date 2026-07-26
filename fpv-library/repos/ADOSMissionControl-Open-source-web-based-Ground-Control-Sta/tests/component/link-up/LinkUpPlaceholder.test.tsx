/**
 * Render test for the reusable LinkUpPlaceholder: each variant shows its
 * headline + the right CTA, and copy interpolates the surface/last-seen values.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "../../helpers/intl-wrapper";
import { LinkUpPlaceholder } from "@/components/shared/link-up/LinkUpPlaceholder";

describe("LinkUpPlaceholder", () => {
  it("locked: names the surface and offers Pair + the value props", () => {
    renderWithIntl(<LinkUpPlaceholder variant="locked" surface="Scripts" />);
    expect(screen.getByText(/unlock Scripts/i)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /pair a companion computer/i }),
    ).toBeTruthy();
    // value-prop list renders the headline companion-computer extras
    expect(screen.getByText(/Long range radio/i)).toBeTruthy();
    expect(screen.getByText(/4G telemetry/i)).toBeTruthy();
  });

  it("agent-offline: shows the offline headline, last-seen, and Reconnect", () => {
    renderWithIntl(
      <LinkUpPlaceholder variant="agent-offline" lastSeenLabel="12s ago" />,
    );
    expect(screen.getByText(/agent offline/i)).toBeTruthy();
    expect(screen.getByText(/12s ago/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /reconnect/i })).toBeTruthy();
  });

  it("no-camera: shows the capability-missing headline", () => {
    renderWithIntl(<LinkUpPlaceholder variant="no-camera" />);
    expect(screen.getByText(/no camera detected/i)).toBeTruthy();
  });

  it("no-connection: offers both the FC and the companion-computer paths", () => {
    renderWithIntl(<LinkUpPlaceholder variant="no-connection" />);
    expect(
      screen.getByRole("button", { name: /connect flight controller/i }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /pair a companion computer/i }),
    ).toBeTruthy();
  });

  it("fc-unverified: interpolates the advertised port and baud", () => {
    renderWithIntl(
      <LinkUpPlaceholder
        variant="fc-unverified"
        fcPort="/dev/ttyAMA0"
        fcBaud={921600}
      />,
    );
    expect(screen.getByText(/\/dev\/ttyAMA0/)).toBeTruthy();
    expect(screen.getByText(/921600/)).toBeTruthy();
  });

  it("stale-pairing: offers Re-pair + Remove and never the USB connect prompt", () => {
    renderWithIntl(
      <LinkUpPlaceholder
        variant="stale-pairing"
        onPrimary={() => {}}
        onSecondary={() => {}}
      />,
    );
    expect(screen.getByText(/needs re-pairing/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /re-pair node/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /remove node/i })).toBeTruthy();
    // The misleading "connect a flight controller" CTA must be gone here.
    expect(
      screen.queryByRole("button", { name: /connect flight controller/i }),
    ).toBeNull();
  });
});
