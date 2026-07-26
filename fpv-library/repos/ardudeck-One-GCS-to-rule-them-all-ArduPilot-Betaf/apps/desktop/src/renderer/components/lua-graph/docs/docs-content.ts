/**
 * Documentation content for the Lua Graph Editor.
 * Each section imports its content from a .md file.
 */
import {
  Rocket,
  Cpu,
  Cable,
  BookOpen,
  Code2,
  Cog,
  Lightbulb,
} from 'lucide-react';
import type { DocSection } from './docs-types';

import gettingStarted from './getting-started.md?raw';
import nodeReference from './node-reference.md?raw';
import connections from './connections.md?raw';
import examples from './examples.md?raw';
import apiReference from './api-reference.md?raw';
import compilation from './compilation.md?raw';
import tipsAndLimitations from './tips-and-limitations.md?raw';

export const DOC_SECTIONS: DocSection[] = [
  { id: 'getting-started', title: 'Getting Started', icon: Rocket, content: gettingStarted },
  { id: 'node-reference', title: 'Node Reference', icon: Cpu, content: nodeReference },
  { id: 'connections', title: 'Connections', icon: Cable, content: connections },
  { id: 'examples', title: 'Examples', icon: BookOpen, content: examples },
  { id: 'api-reference', title: 'ArduPilot API', icon: Code2, content: apiReference },
  { id: 'compilation', title: 'Compilation', icon: Cog, content: compilation },
  { id: 'tips', title: 'Tips & Limits', icon: Lightbulb, content: tipsAndLimitations },
];
