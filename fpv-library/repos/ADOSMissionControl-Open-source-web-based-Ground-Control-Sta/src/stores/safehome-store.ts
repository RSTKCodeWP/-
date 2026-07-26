/**
 * @module safehome-store
 * @description Zustand store for iNav safehome slots.
 * Manages 16 safehome positions: read from FC, edit locally, write back.
 * @license GPL-3.0-only
 */

import { create } from 'zustand'
import type { DroneProtocol } from '@/lib/protocol/types'
import type { INavSafehome } from '@/lib/protocol/msp/msp-decoders-inav'
import { formatErrorMessage } from '@/lib/utils'

/** Total safehome slots iNav supports. */
export const SAFEHOME_MAX = 16

function defaultSafehome(index: number): INavSafehome {
  return { index, enabled: false, lat: 0, lon: 0 }
}

function defaultSlots(): INavSafehome[] {
  return Array.from({ length: SAFEHOME_MAX }, (_, i) => defaultSafehome(i))
}

interface SafehomeStoreState {
  safehomes: INavSafehome[]
  activeIndex: number | null
  loading: boolean
  error: string | null
  dirty: boolean

  // Actions
  setSlot: (index: number, partial: Partial<Omit<INavSafehome, 'index'>>) => void
  toggleEnabled: (index: number) => void
  setActiveIndex: (index: number | null) => void
  clear: () => void
  loadFromFc: (protocol: DroneProtocol) => Promise<void>
  uploadToFc: (protocol: DroneProtocol) => Promise<void>
}

export const useSafehomeStore = create<SafehomeStoreState>((set, get) => ({
  safehomes: defaultSlots(),
  activeIndex: null,
  loading: false,
  error: null,
  dirty: false,

  setSlot(index, partial) {
    const safehomes = [...get().safehomes]
    safehomes[index] = { ...safehomes[index], ...partial }
    set({ safehomes, dirty: true })
  },

  toggleEnabled(index) {
    const safehomes = [...get().safehomes]
    safehomes[index] = { ...safehomes[index], enabled: !safehomes[index].enabled }
    set({ safehomes, dirty: true })
  },

  setActiveIndex(index) {
    set({ activeIndex: index })
  },

  clear() {
    set({ safehomes: defaultSlots(), activeIndex: null, loading: false, error: null, dirty: false })
  },

  async loadFromFc(protocol) {
    if (get().loading) return
    if (!protocol.downloadSafehomes) {
      set({ error: 'Safehomes not supported by this firmware' })
      return
    }
    set({ loading: true, error: null })
    try {
      const result = await protocol.downloadSafehomes()
      // Pad to 16 slots
      const safehomes = defaultSlots()
      for (const sh of result) {
        if (sh.index >= 0 && sh.index < SAFEHOME_MAX) {
          safehomes[sh.index] = sh
        }
      }
      set({ safehomes, loading: false, dirty: false })
    } catch (err) {
      set({ loading: false, error: formatErrorMessage(err) })
    }
  },

  async uploadToFc(protocol) {
    if (get().loading) return
    if (!protocol.uploadSafehomes) {
      set({ error: 'Safehomes not supported by this firmware' })
      return
    }
    set({ loading: true, error: null })
    try {
      const result = await protocol.uploadSafehomes(get().safehomes)
      if (result.success) {
        set({ loading: false, dirty: false })
      } else {
        set({ loading: false, error: result.message })
      }
    } catch (err) {
      set({ loading: false, error: formatErrorMessage(err) })
    }
  },
}))
