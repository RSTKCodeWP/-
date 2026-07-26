/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { DronePart, DroneConfig } from "../types";

export const FRAMES: DronePart[] = [
  {
    id: "apex-5",
    name: "APEX EVO 5\" HD",
    category: "frame",
    weight: 125,
    price: 139,
    specs: {
      "Material": "Toray T700 Carbon Fiber",
      "Wheelbase": "225 mm",
      "Arm Thickness": "5.5 mm",
      "Top Plate": "2.0 mm",
      "Prop Size": "5 inch",
      "Max Speed": "175 km/h"
    },
    description: "The absolute standard for elite freestyle. Built with unmatched crash resilience, structural stiffness, and vibration isolation for butter-smooth HD footage."
  },
  {
    id: "scythe-6",
    name: "SCYTHE LONG-RANGE 6\"",
    category: "frame",
    weight: 148,
    price: 159,
    specs: {
      "Material": "Unidirectional Carbon",
      "Wheelbase": "260 mm",
      "Arm Thickness": "6.0 mm",
      "Top Plate": "2.5 mm",
      "Prop Size": "6 inch",
      "Max Speed": "190 km/h"
    },
    description: "Sleek, low-drag profile engineered specifically for medium-range cruising and mountain surfing. Extends flight time with advanced aerodynamics."
  },
  {
    id: "screamer-5",
    name: "SCREAMER F1 ULTRA-LIGHT",
    category: "frame",
    weight: 71,
    price: 119,
    specs: {
      "Material": "Kevlar-Reinforced Carbon",
      "Wheelbase": "215 mm",
      "Arm Thickness": "4.5 mm",
      "Top Plate": "1.5 mm",
      "Prop Size": "5 inch",
      "Max Speed": "215 km/h"
    },
    description: "Stripped-back competition layout for pure racing adrenaline. Unbelievable power-to-weight ratio designed specifically to dominate tight racing tracks."
  }
];

export const MOTORS: DronePart[] = [
  {
    id: "xing2-2207",
    name: "T-MOTOR F60 PRO V (1950KV)",
    category: "motor",
    weight: 33, // per motor (will multiply by 4 in summary)
    price: 112, // set of 4
    specs: {
      "Stator Size": "2207",
      "KV Rating": "1950 KV",
      "Cells (LiPo)": "6S (22.2V)",
      "Peak Thrust": "2.1 kg",
      "Shaft": "Titanium Alloy",
      "Magnets": "N52SH Curved"
    },
    description: "The gold standard for high-thrust 6S freestyle. Legendary durability with titanium shafts and premium EZO bearings for explosive punching power."
  },
  {
    id: "vortex-2306",
    name: "APEX VORTEX 2306.5 (1800KV)",
    category: "motor",
    weight: 31,
    price: 104,
    specs: {
      "Stator Size": "2306.5",
      "KV Rating": "1800 KV",
      "Cells (LiPo)": "6S (22.2V)",
      "Peak Thrust": "1.85 kg",
      "Shaft": "Steel/Hollow",
      "Magnets": "N52H Arc"
    },
    description: "Optimized for butter-smooth mid-throttle control. Features linear response curves, perfect for precision cinematic orbits and flowing mountain dives."
  },
  {
    id: "hyper-2208",
    name: "HYPERGRAVITY 2208 (2450KV)",
    category: "motor",
    weight: 36,
    price: 128,
    specs: {
      "Stator Size": "2208",
      "KV Rating": "2450 KV",
      "Cells (LiPo)": "4S-6S",
      "Peak Thrust": "2.45 kg",
      "Shaft": "Hollow Titanium",
      "Magnets": "N55 Super-Neodymium"
    },
    description: "Brutal, uncompromising drag racing motors. High-mass stator for massive continuous thermal capability and unparalleled top-end velocity."
  }
];

export const PROPS: DronePart[] = [
  {
    id: "hq-s5",
    name: "GEMFAN HURRICANE 51466 V2",
    category: "props",
    weight: 4, // set of 4
    price: 18,
    specs: {
      "Diameter": "5.1 inch",
      "Pitch": "4.66 inch",
      "Blades": "3 (Tri-Blade)",
      "Material": "Polycarbonate",
      "Grip Style": "Aggressive Bite",
      "Inertia": "Medium-High"
    },
    description: "High-pitch racing props offering exceptional top-end velocity and swift recovery times. Delivers sharp cornering response with zero propwash."
  },
  {
    id: "ethix-s4",
    name: "HQPROP ETHIX S5 PEACH",
    category: "props",
    weight: 3.8,
    price: 16,
    specs: {
      "Diameter": "5.0 inch",
      "Pitch": "3.7 inch",
      "Blades": "3 (Tri-Blade)",
      "Material": "Thin Polycarbonate",
      "Grip Style": "Linelike Smoothness",
      "Inertia": "Ultra-Low"
    },
    description: "Designed by FPV legends for ultimate flow and cinematic smoothness. Low pitch feels extremely linear and eliminates camera vibrations."
  },
  {
    id: "azure-5150",
    name: "AZURE POWER 5150 BRUTAL",
    category: "props",
    weight: 4.2,
    price: 22,
    specs: {
      "Diameter": "5.1 inch",
      "Pitch": "5.0 inch",
      "Blades": "3 (Tri-Blade)",
      "Material": "Glass-Fiber Polycarbonate",
      "Grip Style": "Instant Grip",
      "Inertia": "High"
    },
    description: "Extreme acceleration. Glass-fiber blend ensures the blades never bend under peak loads, giving direct mechanical feedback at up to 40,000 RPM."
  }
];

export const VTXS: DronePart[] = [
  {
    id: "dji-o3",
    name: "DJI O3 AIR UNIT DIGITAL HD",
    category: "vtx",
    weight: 39,
    price: 249,
    specs: {
      "Resolution": "1080p 120fps",
      "Latency": "28 ms",
      "Max Range": "10 km (FCC)",
      "Onboard Recording": "4K 60fps / 20GB",
      "RF Power": "Up to 1.5W",
      "Antenna": "Dual Polarized LHCP"
    },
    description: "State-of-the-art digital video feed and heavy-duty camera. Stream ultra-crisp 1080p feed into DJI Goggles 2 while recording raw stabilized 4K footage."
  },
  {
    id: "walksnail-v2",
    name: "WALKSNAIL AVATAR PRO V2",
    category: "vtx",
    weight: 26,
    price: 189,
    specs: {
      "Resolution": "1080p 100fps",
      "Latency": "22 ms",
      "Max Range": "8 km",
      "Onboard Recording": "1080p Starlight",
      "RF Power": "Up to 1.2W",
      "Antenna": "Single LHCP Omni"
    },
    description: "Incredible low-light starlight camera and lightweight digital VTX. Excels in starlight operations and tight indoor environments with negligible static."
  },
  {
    id: "tbs-analog",
    name: "TBS UNIFY PRO32 + RAPIDFIRE ANALOG",
    category: "vtx",
    weight: 12,
    price: 129,
    specs: {
      "Resolution": "Analog / NTSC-PAL",
      "Latency": "0 ms (Instant)",
      "Max Range": "12 km",
      "Onboard Recording": "Goggle DVR Required",
      "RF Power": "Up to 1.0W (SmartAudio)",
      "Antenna": "RHCP Stubby"
    },
    description: "Old-school pure analog setup with zero-latency transmission. Features the legendary ImmersionRC RapidFire receiver simulation for lightning-fast feedback."
  }
];

export const DEFAULT_CONFIG: DroneConfig = {
  frame: FRAMES[0],
  motor: MOTORS[0],
  props: PROPS[0],
  vtx: VTXS[0]
};
