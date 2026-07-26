import { describe, it, expect } from 'vitest';
import {
  createManualGroup,
  createImportedGroup,
  createSurveyGroup,
  isManualGroup,
  isSurveyGroup,
  isImportedGroup,
  nextGroupColor,
  GROUP_COLOR_PALETTE,
} from './mission-group-types';

describe('createManualGroup', () => {
  it('creates a manual-kind group with a uuid id', () => {
    const g = createManualGroup();
    expect(g.kind).toBe('manual');
    expect(g.id).toMatch(/[0-9a-f-]{8,}/);
  });

  it('defaults name to "Manual" and color to first palette entry', () => {
    const g = createManualGroup();
    expect(g.name).toBe('Manual');
    expect(g.color).toBe(GROUP_COLOR_PALETTE[0]);
  });

  it('respects supplied overrides', () => {
    const g = createManualGroup({ name: 'Custom', color: '#abcdef', order: 7 });
    expect(g.name).toBe('Custom');
    expect(g.color).toBe('#abcdef');
    expect(g.order).toBe(7);
  });

  it('defaults visible to true and collapsed to false', () => {
    const g = createManualGroup();
    expect(g.visible).toBe(true);
    expect(g.collapsed).toBe(false);
  });
});

describe('createImportedGroup', () => {
  it('creates an imported-kind group that is visible by default', () => {
    const g = createImportedGroup({ importedFrom: 'fc', sourceLabel: 'Vehicle mission' });
    expect(g.kind).toBe('imported');
    expect(g.importedFrom).toBe('fc');
    expect(g.sourceLabel).toBe('Vehicle mission');
    // Just-downloaded groups are shown on the map so the user can see what
    // they pulled. Upload is a separate per-group action.
    expect(g.visible).toBe(true);
  });
});

describe('createSurveyGroup', () => {
  it('creates a survey-kind group carrying polygon + config', () => {
    const g = createSurveyGroup({
      name: 'North field',
      generatorId: 'builtin.grid',
      generatorVersion: '1.0.0',
      polygon: [{ lat: 1, lng: 2 }, { lat: 3, lng: 4 }, { lat: 5, lng: 6 }],
      config: { altitude: 80, speed: 5 },
    });
    expect(g.kind).toBe('survey');
    expect(g.generatorId).toBe('builtin.grid');
    expect(g.polygon).toHaveLength(3);
    expect(g.config).toEqual({ altitude: 80, speed: 5 });
    expect(g.lastGeneratedAt).toBeNull();
    expect(g.lastGeneratedSignature).toBeNull();
  });
});

describe('type guards', () => {
  it('isManualGroup matches only manual groups', () => {
    expect(isManualGroup(createManualGroup())).toBe(true);
    expect(isManualGroup(createImportedGroup({ importedFrom: 'fc', sourceLabel: 'X' }))).toBe(false);
  });

  it('isSurveyGroup matches only survey groups', () => {
    expect(
      isSurveyGroup(
        createSurveyGroup({
          name: 'X',
          generatorId: 'g',
          generatorVersion: 'v',
          polygon: [],
          config: {},
        }),
      ),
    ).toBe(true);
    expect(isSurveyGroup(createManualGroup())).toBe(false);
  });

  it('isImportedGroup matches only imported groups', () => {
    expect(isImportedGroup(createImportedGroup({ importedFrom: 'fc', sourceLabel: 'X' }))).toBe(true);
    expect(isImportedGroup(createManualGroup())).toBe(false);
  });
});

describe('nextGroupColor', () => {
  it('returns the first palette entry when nothing exists', () => {
    expect(nextGroupColor([])).toBe(GROUP_COLOR_PALETTE[0]);
  });

  it('picks an unused color before recycling', () => {
    const g1 = createManualGroup({ color: GROUP_COLOR_PALETTE[0] });
    const g2 = createManualGroup({ color: GROUP_COLOR_PALETTE[1] });
    const g3 = createManualGroup({ color: GROUP_COLOR_PALETTE[2] });
    const next = nextGroupColor([g1, g2, g3]);
    expect(GROUP_COLOR_PALETTE).toContain(next);
    expect(next).not.toBe(GROUP_COLOR_PALETTE[0]);
    expect(next).not.toBe(GROUP_COLOR_PALETTE[1]);
    expect(next).not.toBe(GROUP_COLOR_PALETTE[2]);
  });

  it('cycles back to least-used when palette is exhausted', () => {
    const groups = GROUP_COLOR_PALETTE.map((c) => createManualGroup({ color: c }));
    // Every color used once; one more group of color[0] makes color[0] heaviest.
    groups.push(createManualGroup({ color: GROUP_COLOR_PALETTE[0] }));
    const next = nextGroupColor(groups);
    // Should never recommend the doubly-used color.
    expect(next).not.toBe(GROUP_COLOR_PALETTE[0]);
  });
});
