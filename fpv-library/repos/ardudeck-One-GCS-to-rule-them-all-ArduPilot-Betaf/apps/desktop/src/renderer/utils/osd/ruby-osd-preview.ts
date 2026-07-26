/**
 * RubyFPV OSD preview layout - approximates how RubyFPV auto-arranges enabled
 * elements so ArduDeck can show a recognisable, layout-faithful preview. This
 * is NOT pixel-exact to the goggles (RubyFPV draws with its own fonts/gauges on
 * the ground unit; ArduDeck does not ship those - see the license-clean rule);
 * the live RubyFPV video feed is the exact-pixel truth. Pure data + one builder
 * so it can be unit-tested and rendered by RubyOsdPreview.
 */

import { RUBY_OSD_ELEMENTS, isElementEnabled, type RubyOsdParams } from './ruby-osd';

/** Nine screen zones: top/middle/bottom x left/center/right. */
export type PreviewZone = 'TL' | 'TC' | 'TR' | 'ML' | 'MR' | 'BL' | 'BC' | 'BR';

/** Elements drawn as vector graphics/overlays rather than text chips. */
export const RUBY_VECTOR_IDS = new Set<string>([
  'horizon', 'heading', 'speed_alt', 'alt_graph', 'instruments', 'ahi_heading', 'speed_to_sides',
  'grid_crosshair', 'grid_diagonal', 'grid_squares', 'grid_thirds',
]);

/** Which zone each text element lands in (RubyFPV-like arrangement). */
export const RUBY_PREVIEW_ZONE: Record<string, PreviewZone> = {
  flight_mode: 'TL', flight_mode_change: 'TL',
  video_mbps: 'TL', video_mode: 'TL', video_bitrate_history: 'TL', cpu_info: 'TL',
  radio_links: 'TC', vehicle_radio_links: 'TC', radio_interfaces: 'TC',
  link_quality_bars: 'TC', link_quality_numbers: 'TC', tx_power: 'TC',
  time: 'TR', battery: 'TR', battery_cells: 'TR', signal_bars: 'TR', rc_rssi: 'TR',
  ground_speed: 'ML', air_speed: 'ML', pitch: 'ML',
  altitude: 'MR', vertical_speed: 'MR',
  gps_info: 'BL', gps_position: 'BL', throttle: 'BL',
  distance: 'BC', total_distance: 'BC', home: 'BC',
  time_lower: 'BR', wind: 'BR', fc_temperature: 'BR', efficiency: 'BR',
};

/** Representative sample readouts for the preview (layout demo, not live). */
export const RUBY_PREVIEW_SAMPLE: Record<string, string> = {
  flight_mode: 'STAB', flight_mode_change: 'STAB',
  video_mbps: '18 Mbps', video_mode: '1080p60', video_bitrate_history: 'BR HIST', cpu_info: 'CPU 42%',
  radio_links: 'LNK', vehicle_radio_links: 'V-LNK', radio_interfaces: 'RX/TX',
  link_quality_bars: 'Q ▮▮▮', link_quality_numbers: 'Q 98%', tx_power: 'TX 25',
  time: '12:34', battery: '22.4V', battery_cells: '3.73V', signal_bars: '▮▮▮', rc_rssi: 'RC 95',
  ground_speed: 'GS 12', air_speed: 'AS 14', pitch: 'P 3°',
  altitude: 'ALT 123m', vertical_speed: 'VS 1.2',
  gps_info: 'GPS 14', gps_position: '47.12 8.65', throttle: 'THR 46%',
  distance: 'D 340m', total_distance: 'TOT 1.2km', home: 'H 340m',
  time_lower: '12:34', wind: 'W 6', fc_temperature: 'FC 42°C', efficiency: 'EFF',
};

export interface RubyPreviewChip {
  id: string;
  label: string;
  text: string;
  zone: PreviewZone;
}

export interface RubyPreview {
  chips: RubyPreviewChip[];
  horizon: boolean;
  heading: boolean;
  speedAlt: boolean;
  altGraph: boolean;
  crosshair: boolean;
  gridDiagonal: boolean;
  gridSquares: boolean;
  gridThirds: boolean;
}

/** Build the preview for a given screen from the enabled elements. */
export function buildRubyPreview(params: RubyOsdParams, screen: number): RubyPreview {
  const chips: RubyPreviewChip[] = [];
  for (const el of RUBY_OSD_ELEMENTS) {
    if (!isElementEnabled(params, screen, el.id)) continue;
    if (RUBY_VECTOR_IDS.has(el.id)) continue;
    const zone = RUBY_PREVIEW_ZONE[el.id];
    if (!zone) continue;
    chips.push({ id: el.id, label: el.label, text: RUBY_PREVIEW_SAMPLE[el.id] ?? el.label, zone });
  }
  const on = (id: string): boolean => isElementEnabled(params, screen, id);
  return {
    chips,
    horizon: on('horizon') || on('instruments'),
    heading: on('heading'),
    speedAlt: on('speed_alt'),
    altGraph: on('alt_graph'),
    crosshair: on('grid_crosshair'),
    gridDiagonal: on('grid_diagonal'),
    gridSquares: on('grid_squares'),
    gridThirds: on('grid_thirds'),
  };
}
