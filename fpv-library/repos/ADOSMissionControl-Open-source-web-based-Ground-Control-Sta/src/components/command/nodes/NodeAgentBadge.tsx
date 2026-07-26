"use client";

/**
 * @module nodes/NodeAgentBadge
 * @description The at-a-glance "FC + SBC" badge shown on a companion-paired drone
 * row (a drone with an onboard computer running the ADOS agent) — the visible
 * differentiator from an FC-only drone. The rich companion summary now lives on
 * the whole-row hover card (NodeStatusHoverCard); this is just the marker.
 * @license GPL-3.0-only
 */

import { Cpu } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function NodeAgentBadge() {
  return (
    <Badge variant="success" className="gap-1 rounded normal-case tracking-normal">
      <Cpu size={9} />
      FC + SBC
    </Badge>
  );
}
