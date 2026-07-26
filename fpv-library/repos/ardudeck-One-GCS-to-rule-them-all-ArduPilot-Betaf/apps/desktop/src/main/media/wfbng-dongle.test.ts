import { describe, it, expect } from 'vitest';
import { findDongleMac, findDongleLinux, findDongleWindows, buildReceiverArgs } from './wfbng-dongle.js';

describe('wfb-ng dongle detection parsers', () => {
  it('finds the RTL8812AU in system_profiler JSON (real capture shape)', () => {
    const json = JSON.stringify({
      SPUSBDataType: [
        {
          _name: 'USB 3.1 Bus',
          _items: [
            { _name: 'Some Hub', vendor_id: '0x05ac', product_id: '0x1234' },
            { _name: '802.11n NIC', vendor_id: '0x0bda', product_id: '0x8812' },
          ],
        },
      ],
    });
    const d = findDongleMac(json)!;
    expect(d).toMatchObject({ vendorId: 0x0bda, productId: 0x8812, name: '802.11n NIC' });
  });

  it('returns null when no supported dongle is present (mac)', () => {
    const json = JSON.stringify({ SPUSBDataType: [{ _name: 'Bus', _items: [{ vendor_id: '0x10c4', product_id: '0xea60' }] }] });
    expect(findDongleMac(json)).toBeNull();
    expect(findDongleMac('not json')).toBeNull();
  });

  it('finds the dongle in lsusb output', () => {
    const out = [
      'Bus 001 Device 002: ID 8087:0024 Intel Corp. Integrated Rate Matching Hub',
      'Bus 002 Device 004: ID 0bda:8812 Realtek Semiconductor Corp. RTL8812AU 802.11a/b/g/n/ac',
    ].join('\n');
    const d = findDongleLinux(out)!;
    expect(d.productId).toBe(0x8812);
    expect(d.name).toContain('RTL8812AU');
    expect(findDongleLinux('Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub')).toBeNull();
  });

  it('finds the dongle in Windows PnP instance ids', () => {
    expect(findDongleWindows('USB\\VID_0BDA&PID_8812\\123456')?.productId).toBe(0x8812);
    expect(findDongleWindows('USB\\VID_0BDA&PID_881A\\1')?.productId).toBe(0x881a);
    expect(findDongleWindows('USB\\VID_10C4&PID_EA60\\0001')).toBeNull();
  });

  it('builds the receiver contract args', () => {
    const args = buildReceiverArgs({ gsKeyPath: '/keys/gs.key', channel: 161, bandwidth: 20, outputPort: 5600 });
    expect(args).toEqual(['--key', '/keys/gs.key', '--channel', '161', '--bandwidth', '20', '--output', 'udp://127.0.0.1:5600']);
  });
});
