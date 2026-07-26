import { describe, it, expect } from 'vitest';
import type { Node, Edge } from '@xyflow/react';
import type { GraphNodeData, GraphEdgeData } from './lua-graph-types';
import { compileGraph } from './lua-compiler';
import { getNodeDefinition } from './node-library';
import { GRAPH_TEMPLATES } from './graph-templates';

function node(
  id: string,
  definitionType: string,
  propertyValues: Record<string, number | boolean | string> = {},
): Node<GraphNodeData> {
  const def = getNodeDefinition(definitionType);
  return {
    id,
    type: definitionType,
    position: { x: 0, y: 0 },
    data: {
      definitionType,
      label: def?.label ?? definitionType,
      category: def?.category ?? 'flow',
      propertyValues,
    },
  };
}

function edge(
  id: string,
  source: string,
  sourceHandle: string,
  target: string,
  targetHandle: string,
): Edge<GraphEdgeData> {
  return { id, source, target, sourceHandle, targetHandle };
}

describe('new watchdog nodes', () => {
  it('sensor-param-get reads a named param with a numeric fallback', () => {
    const nodes = [node('p', 'sensor-param-get', { param_name: 'CAM1_TRIGG_DIST' })];
    const res = compileGraph(nodes, [], 'test');
    expect(res.success).toBe(true);
    expect(res.code).toContain('param:get("CAM1_TRIGG_DIST")');
    expect(res.code).toContain('or 0');
  });

  it('sensor-gpio-read reads the pin as an integer and guards a negative/nil pin', () => {
    const nodes = [node('g', 'sensor-gpio-read', { pin: 54 })];
    const res = compileGraph(nodes, [], 'test');
    expect(res.success).toBe(true);
    expect(res.code).toContain('gpio:read(math.floor(');
    // gpio:read returns a boolean on real firmware — must be normalized to 0/1
    expect(res.code).toContain('== true');
  });

  it('sensor-pwm-pulse sets up PWMSource once in the prelude and drains it per tick', () => {
    const nodes = [node('p', 'sensor-pwm-pulse', { pin: 54 })];
    const res = compileGraph(nodes, [], 'test');
    expect(res.success).toBe(true);
    // one-time setup at module scope, before update()
    const updateIdx = res.code.indexOf('function update()');
    expect(res.code.indexOf('PWMSource()')).toBeGreaterThan(-1);
    expect(res.code.indexOf('PWMSource()')).toBeLessThan(updateIdx);
    expect(res.code.indexOf(':set_pin(54)')).toBeLessThan(updateIdx);
    // per-tick read inside update()
    expect(res.code.indexOf(':get_pwm_us()')).toBeGreaterThan(updateIdx);
    // failed attach is reported, not silent
    expect(res.code).toContain('not usable');
  });

  it('sensor-gpio-read takes its pin from a wired input when connected', () => {
    const nodes = [
      node('pin', 'sensor-param-get', { param_name: 'CAM1_FEEDBAK_PIN' }),
      node('g', 'sensor-gpio-read', { pin: 54 }),
    ];
    const edges = [edge('e', 'pin', 'value', 'g', 'pin')];
    const res = compileGraph(nodes, edges, 'test');
    expect(res.success).toBe(true);
    expect(res.code).toContain('param:get("CAM1_FEEDBAK_PIN")');
    // the wired param value, not the literal 54, feeds gpio:read
    expect(res.code).not.toContain('gpio:read(math.floor(54))');
  });

  it('timing-watchdog accumulates time and expires after the timeout', () => {
    const nodes = [node('w', 'timing-watchdog', { timeout_ms: 3000 })];
    const res = compileGraph(nodes, [], 'test', 10);
    expect(res.success).toBe(true);
    expect(res.code).toContain('>= 3000');
    // resets on kick, accumulates the entry interval otherwise
    expect(res.code).toContain('+ 10');
  });

  it('sensor-current-waypoint exposes the current nav index', () => {
    const nodes = [node('wp', 'sensor-current-waypoint')];
    const res = compileGraph(nodes, [], 'test');
    expect(res.success).toBe(true);
    expect(res.code).toContain('mission:get_current_nav_index()');
  });

  it('action-gcs-text appends a wired numeric value to the message', () => {
    const nodes = [
      node('wp', 'sensor-current-waypoint'),
      node('t', 'action-gcs-text', { message: 'WP ', severity: 4 }),
    ];
    const edges = [edge('e', 'wp', 'index', 't', 'value')];
    const res = compileGraph(nodes, edges, 'test');
    expect(res.success).toBe(true);
    expect(res.code).toContain('.. tostring(');
  });

  it('action-gcs-text stays a plain string when no value is wired', () => {
    const nodes = [node('t', 'action-gcs-text', { message: 'hi', severity: 6 })];
    const res = compileGraph(nodes, [], 'test');
    expect(res.success).toBe(true);
    expect(res.code).not.toContain('.. tostring(');
  });
});

describe('Camera Trigger Watchdog template', () => {
  it('is registered and compiles to valid-looking Lua', () => {
    const tpl = GRAPH_TEMPLATES.find((t) => t.id === 'camera-trigger-watchdog');
    expect(tpl).toBeDefined();
    const g = tpl!.graph;
    const res = compileGraph(g.nodes as Node<GraphNodeData>[], g.edges as Edge<GraphEdgeData>[], g.name, g.runIntervalMs);
    expect(res.success).toBe(true);
    expect(res.errors).toEqual([]);
    expect(res.code).toContain('mission:get_current_nav_index()');
    expect(res.code).toContain('param:get("CAM1_TRIGG_DIST")');
  });

  it('detects photos via PWMSource interrupt, not gpio:read polling', () => {
    const tpl = GRAPH_TEMPLATES.find((t) => t.id === 'camera-trigger-watchdog');
    const g = tpl!.graph;
    // hotshoe pulses are 1-2 ms; gpio:read polling misses them
    expect(g.runIntervalMs).toBeGreaterThanOrEqual(50);
    const res = compileGraph(g.nodes as Node<GraphNodeData>[], g.edges as Edge<GraphEdgeData>[], g.name, g.runIntervalMs);
    expect(res.code).toContain('PWMSource()');
    expect(res.code).toContain(':get_pwm_us()');
    expect(res.code).not.toContain('gpio:read');
    // must not steal AP_Camera's feedback pin (comment text may mention it)
    expect(res.code).not.toContain('param:get("CAM1_FEEDBAK_PIN")');
  });
});
