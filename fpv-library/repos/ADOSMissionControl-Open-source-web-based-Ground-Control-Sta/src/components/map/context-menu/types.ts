/**
 * @module map/context-menu/types
 * @description Shared types for the right-click flight map menu.
 * @license GPL-3.0-only
 */

export interface MenuPosition {
  x: number;
  y: number;
  lat: number;
  lon: number;
}

export interface MenuItemDef {
  id: string;
  label: string;
  icon: string;
  group: number;
  shortcut?: string;
  danger?: boolean;
}
