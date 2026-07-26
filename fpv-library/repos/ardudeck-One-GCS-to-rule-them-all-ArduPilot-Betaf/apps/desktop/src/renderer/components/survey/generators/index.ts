/**
 * Built-in survey generator self-registration.
 *
 * Importing this module is sufficient to populate the survey generator
 * registry with the bundled generators (grid, crosshatch, circular,
 * spiral, perimeter-fill). The survey-store imports this once at
 * module load.
 */

import { registerSurveyGenerator } from '../generator-registry';
import { generateGrid } from './grid-generator';
import { generateCrosshatch } from './crosshatch-generator';
import { generateCircular } from './circular-generator';
import { generateSpiral } from './spiral-generator';
import { generatePerimeterFill } from './perimeter-fill-generator';
import { generateCorridor } from './corridor-generator';

registerSurveyGenerator({
  id: 'builtin.grid',
  version: '1.0.0',
  displayName: 'Grid',
  description:
    'Boustrophedon lawnmower pattern. Parallel scan lines across the polygon with overshoot for turns.',
  capabilities: {
    supportsHoles: true,
    supportsWorkspace: false,
    requiresCamera: true,
    isAsync: false,
    isRemote: false,
  },
  generate: generateGrid,
});

registerSurveyGenerator({
  id: 'builtin.crosshatch',
  version: '1.0.0',
  displayName: 'Crosshatch',
  description:
    'Two perpendicular grid passes. Higher photo density and improved 3D reconstruction over a single grid.',
  capabilities: {
    supportsHoles: true,
    supportsWorkspace: false,
    requiresCamera: true,
    isAsync: false,
    isRemote: false,
  },
  generate: generateCrosshatch,
});

registerSurveyGenerator({
  id: 'builtin.circular',
  version: '1.0.0',
  displayName: 'Circular',
  description: 'Orbit a point of interest at fixed radius.',
  capabilities: {
    supportsHoles: false,
    supportsWorkspace: false,
    requiresCamera: true,
    isAsync: false,
    isRemote: false,
  },
  generate: generateCircular,
});

registerSurveyGenerator({
  id: 'builtin.spiral',
  version: '1.0.0',
  displayName: 'Spiral',
  description: 'Inward or outward spiral within the polygon.',
  capabilities: {
    supportsHoles: false,
    supportsWorkspace: false,
    requiresCamera: true,
    isAsync: false,
    isRemote: false,
  },
  generate: generateSpiral,
});

registerSurveyGenerator({
  id: 'builtin.corridor',
  version: '1.0.0',
  displayName: 'Corridor',
  description:
    'Linear survey along a centerline (roads, rail, power lines, pipelines). Parallel strips with plane racetrack turns or copter on-the-spot turns.',
  capabilities: {
    supportsHoles: false,
    supportsWorkspace: false,
    requiresCamera: true,
    isAsync: false,
    isRemote: false,
  },
  generate: generateCorridor,
});

registerSurveyGenerator({
  id: 'builtin.perimeter-fill',
  version: '1.0.0',
  displayName: 'Perimeter Fill',
  description: 'N perimeter passes followed by a grid fill of the interior.',
  capabilities: {
    supportsHoles: false,
    supportsWorkspace: false,
    requiresCamera: true,
    isAsync: false,
    isRemote: false,
  },
  generate: generatePerimeterFill,
});
