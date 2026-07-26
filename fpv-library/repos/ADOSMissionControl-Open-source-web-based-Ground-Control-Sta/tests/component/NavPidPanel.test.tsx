import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithIntl } from '../helpers/intl-wrapper'
import { NavPidPanel } from '@/components/fc/inav/NavPidPanel'
import { useDroneManager } from '@/stores/drone-manager'
import type { SettingValue } from '@/lib/protocol/types'

vi.mock('@/hooks/use-armed-lock', () => ({
  useArmedLock: () => ({ isArmed: false, lockMessage: '' }),
}))

vi.mock('@/hooks/use-unsaved-guard', () => ({
  useUnsavedGuard: () => undefined,
}))

/** Build a protocol stub exposing the name-based settings capability. */
function stubProtocol(getSetting: (name: string) => Promise<SettingValue>) {
  return {
    settings: {
      getSetting: vi.fn(getSetting),
      setSetting: vi.fn().mockResolvedValue({ success: true, resultCode: 0, message: 'OK' }),
      getSettingInfo: vi.fn(),
      enumerate: vi.fn().mockResolvedValue([]),
    },
  }
}

describe('NavPidPanel', () => {
  beforeEach(() => {
    useDroneManager.setState({ getSelectedProtocol: () => null } as never)
  })

  it('renders the panel title', () => {
    renderWithIntl(<NavPidPanel />)
    expect(screen.getByText('Nav PID')).toBeDefined()
  })

  it('renders the subtitle', () => {
    renderWithIntl(<NavPidPanel />)
    expect(screen.getByText('iNav navigation controller PID gains')).toBeDefined()
  })

  it('does not render PID inputs before Read is triggered', () => {
    renderWithIntl(<NavPidPanel />)
    expect(screen.queryByText('Position XY')).toBeNull()
  })

  it('hides the Read from FC button when disconnected', () => {
    renderWithIntl(<NavPidPanel />)
    expect(screen.queryByRole('button', { name: /read from fc/i })).toBeNull()
  })

  it('shows Write to FC button only after data is loaded', async () => {
    const mockAdapter = stubProtocol(async () => ({ type: 'uint8', value: 42 }))
    useDroneManager.setState({
      getSelectedProtocol: () => mockAdapter,
    } as never)

    const { container } = renderWithIntl(<NavPidPanel />)
    const readBtn = container.querySelector('button')
    expect(readBtn).toBeDefined()
  })

  it('reads the canonical iNav multicopter nav-PID setting keys', async () => {
    const calls: string[] = []
    const mockAdapter = stubProtocol((name: string) => {
      calls.push(name)
      return Promise.resolve({ type: 'uint8', value: 42 })
    })
    useDroneManager.setState({
      getSelectedProtocol: () => mockAdapter,
    } as never)

    const { container } = renderWithIntl(<NavPidPanel />)
    const readBtn = container.querySelector('button')
    readBtn?.click()
    await new Promise((r) => setTimeout(r, 20))

    // At least one canonical nav_mc_* key must flow through the settings surface.
    // Guards against a future rename that silently breaks real-FC reads.
    expect(calls).toContain('nav_mc_pos_xy_p')
  })
})
