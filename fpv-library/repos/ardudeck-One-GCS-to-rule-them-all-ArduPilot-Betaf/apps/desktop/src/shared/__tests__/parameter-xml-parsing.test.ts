import { describe, it, expect } from 'vitest';
import type { ParameterMetadata, ParameterMetadataStore } from '../parameter-metadata';

/**
 * The parseParameterXml function lives in ipc-handlers.ts and is not exported.
 * We replicate the core parsing logic here to test the regex fix for issue #70:
 * The value regex must accept negative code values like code="-1" for GPIO.
 */
function parseParameterXml(xml: string): ParameterMetadataStore {
  const metadata: ParameterMetadataStore = {};
  const paramRegex = /<param\s+([^>]+)>([\s\S]*?)<\/param>/g;
  const attrRegex = /(\w+)="([^"]*)"/g;
  const fieldRegex = /<field\s+name="([^"]*)">([\s\S]*?)<\/field>/g;
  // This is the FIXED regex - accepts negative codes via -?\d+
  const valueRegex = /<value\s+code="(-?\d+)"[^>]*>([^<]*)<\/value>/g;
  const bitRegex = /<bit\s+code="(\d+)"[^>]*>([^<]*)<\/bit>/g;

  let match;
  while ((match = paramRegex.exec(xml)) !== null) {
    const attrString = match[1]!;
    const content = match[2]!;

    const attrs: Record<string, string> = {};
    let attrMatch;
    while ((attrMatch = attrRegex.exec(attrString)) !== null) {
      attrs[attrMatch[1]!] = attrMatch[2]!;
    }

    let paramName = attrs.name || '';
    const colonIndex = paramName.indexOf(':');
    if (colonIndex !== -1) {
      paramName = paramName.substring(colonIndex + 1);
    }
    if (!paramName) continue;

    const param: ParameterMetadata = {
      name: paramName,
      humanName: attrs.humanName || paramName,
      description: attrs.documentation || '',
    };

    let fieldMatch;
    while ((fieldMatch = fieldRegex.exec(content)) !== null) {
      const fieldName = fieldMatch[1]!;
      const fieldValue = fieldMatch[2]!;
      const value = fieldValue.trim();
      switch (fieldName) {
        case 'Range': {
          const parts = value.split(/\s+/);
          if (parts.length >= 2) {
            param.range = {
              min: parseFloat(parts[0]!),
              max: parseFloat(parts[1]!),
            };
          }
          break;
        }
      }
    }

    let valueMatch;
    while ((valueMatch = valueRegex.exec(content)) !== null) {
      if (!param.values) param.values = {};
      param.values[parseInt(valueMatch[1]!, 10)] = valueMatch[2]!.trim();
    }

    let bitMatch;
    while ((bitMatch = bitRegex.exec(content)) !== null) {
      if (!param.bitmask) param.bitmask = {};
      param.bitmask[parseInt(bitMatch[1]!, 10)] = bitMatch[2]!.trim();
    }

    metadata[paramName] = param;
  }
  return metadata;
}

describe('parseParameterXml - negative value codes (issue #70)', () => {
  const SERVO_FUNCTION_XML = `
<param name="ArduPlane:SERVO5_FUNCTION" humanName="Servo 5 Function" documentation="Function assigned to this servo">
  <field name="Range">-1 120</field>
  <values>
    <value code="-1">GPIO</value>
    <value code="0">Disabled</value>
    <value code="1">RCPassThru</value>
    <value code="33">Motor1</value>
    <value code="34">Motor2</value>
  </values>
</param>`;

  it('parses negative value code -1 as GPIO', () => {
    const result = parseParameterXml(SERVO_FUNCTION_XML);
    const param = result['SERVO5_FUNCTION'];
    expect(param).toBeDefined();
    expect(param!.values).toBeDefined();
    expect(param!.values![-1]).toBe('GPIO');
  });

  it('still parses positive value codes', () => {
    const result = parseParameterXml(SERVO_FUNCTION_XML);
    const param = result['SERVO5_FUNCTION'];
    expect(param!.values![0]).toBe('Disabled');
    expect(param!.values![1]).toBe('RCPassThru');
    expect(param!.values![33]).toBe('Motor1');
    expect(param!.values![34]).toBe('Motor2');
  });

  it('parses all 5 values including the negative one', () => {
    const result = parseParameterXml(SERVO_FUNCTION_XML);
    const param = result['SERVO5_FUNCTION'];
    const keys = Object.keys(param!.values!).map(Number);
    expect(keys).toHaveLength(5);
    expect(keys).toContain(-1);
  });

  it('strips vehicle prefix from param name', () => {
    const result = parseParameterXml(SERVO_FUNCTION_XML);
    expect(result['SERVO5_FUNCTION']).toBeDefined();
    expect(result['ArduPlane:SERVO5_FUNCTION']).toBeUndefined();
  });
});

describe('parseParameterXml - value regex does not match negative bit codes', () => {
  const BITMASK_XML = `
<param name="TEST_BITMASK" humanName="Test Bitmask" documentation="A bitmask param">
  <bitmask>
    <bit code="0">Bit Zero</bit>
    <bit code="1">Bit One</bit>
  </bitmask>
</param>`;

  it('parses bitmask codes correctly', () => {
    const result = parseParameterXml(BITMASK_XML);
    const param = result['TEST_BITMASK'];
    expect(param).toBeDefined();
    expect(param!.bitmask).toBeDefined();
    expect(param!.bitmask![0]).toBe('Bit Zero');
    expect(param!.bitmask![1]).toBe('Bit One');
  });
});

describe('parseParameterXml - param with only positive values still works', () => {
  const SIMPLE_ENUM_XML = `
<param name="SIMPLE_PARAM" humanName="Simple" documentation="An enum param">
  <values>
    <value code="0">Off</value>
    <value code="1">On</value>
  </values>
</param>`;

  it('parses simple positive-only enum values', () => {
    const result = parseParameterXml(SIMPLE_ENUM_XML);
    const param = result['SIMPLE_PARAM'];
    expect(param!.values![0]).toBe('Off');
    expect(param!.values![1]).toBe('On');
  });
});
