/**
 * Type definitions for Lua Graph Editor documentation sections.
 */
import type { LucideIcon } from 'lucide-react';

export interface DocSection {
  id: string;
  title: string;
  icon: LucideIcon;
  content: string;
}
