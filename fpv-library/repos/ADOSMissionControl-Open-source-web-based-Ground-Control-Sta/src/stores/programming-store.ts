/**
 * @module programming-store
 * @description Zustand store for iNav Programming Framework.
 * Manages logic conditions (64 slots), global variables (8 slots),
 * and programming PIDs (4 slots). Includes live status polling.
 * @license GPL-3.0-only
 */

import { create } from 'zustand'
import type { DroneProtocol } from '@/lib/protocol/types'
import type {
  INavLogicCondition,
  INavLogicConditionsStatus,
  INavGvarStatus,
  INavProgrammingPid,
  INavProgrammingPidStatus,
} from '@/lib/protocol/msp/msp-decoders-inav'
import { formatErrorMessage } from '@/lib/utils'

export const LOGIC_CONDITION_MAX = 64
export const GVAR_MAX = 8
export const PROGRAMMING_PID_MAX = 4

function defaultLogicCondition(): INavLogicCondition {
  return {
    enabled: false,
    activatorId: 0,
    operation: 0,
    operandAType: 0,
    operandAValue: 0,
    operandBType: 0,
    operandBValue: 0,
    flags: 0,
  }
}

function defaultLogicConditions(): INavLogicCondition[] {
  return Array.from({ length: LOGIC_CONDITION_MAX }, () => defaultLogicCondition())
}

function defaultProgrammingPid(): INavProgrammingPid {
  return {
    enabled: false,
    setpointType: 0,
    setpointValue: 0,
    measurementType: 0,
    measurementValue: 0,
    gains: { P: 0, I: 0, D: 0, FF: 0 },
  }
}

function defaultProgrammingPids(): INavProgrammingPid[] {
  return Array.from({ length: PROGRAMMING_PID_MAX }, () => defaultProgrammingPid())
}

interface ProgrammingStoreState {
  conditions: INavLogicCondition[]
  conditionsStatus: INavLogicConditionsStatus[]
  gvarStatus: INavGvarStatus
  pids: INavProgrammingPid[]
  pidStatus: INavProgrammingPidStatus[]

  loading: boolean
  error: string | null
  conditionsDirty: boolean
  pidsDirty: boolean

  pollingTimer: ReturnType<typeof setInterval> | null

  setCondition: (index: number, partial: Partial<INavLogicCondition>) => void
  setPid: (index: number, partial: Partial<INavProgrammingPid>) => void
  loadConditions: (conditions: INavLogicCondition[]) => void
  clear: () => void

  loadFromFc: (protocol: DroneProtocol) => Promise<void>
  uploadConditions: (protocol: DroneProtocol) => Promise<void>
  uploadPids: (protocol: DroneProtocol) => Promise<void>
  writeGvar: (protocol: DroneProtocol, index: number, value: number) => Promise<void>

  startPolling: (protocol: DroneProtocol, intervalMs?: number) => void
  stopPolling: () => void
  pollStatus: (protocol: DroneProtocol) => Promise<void>
}

export const useProgrammingStore = create<ProgrammingStoreState>((set, get) => ({
  conditions: defaultLogicConditions(),
  conditionsStatus: [],
  gvarStatus: { values: [] },
  pids: defaultProgrammingPids(),
  pidStatus: [],

  loading: false,
  error: null,
  conditionsDirty: false,
  pidsDirty: false,

  pollingTimer: null,

  setCondition(index, partial) {
    const conditions = [...get().conditions]
    conditions[index] = { ...conditions[index], ...partial }
    set({ conditions, conditionsDirty: true })
  },

  setPid(index, partial) {
    const pids = [...get().pids]
    pids[index] = { ...pids[index], ...partial }
    set({ pids, pidsDirty: true })
  },

  loadConditions(conditions) {
    const next = defaultLogicConditions()
    conditions.forEach((c, i) => {
      if (i < LOGIC_CONDITION_MAX) next[i] = c
    })
    set({ conditions: next, conditionsDirty: true })
  },

  clear() {
    get().stopPolling()
    set({
      conditions: defaultLogicConditions(),
      conditionsStatus: [],
      gvarStatus: { values: [] },
      pids: defaultProgrammingPids(),
      pidStatus: [],
      loading: false,
      error: null,
      conditionsDirty: false,
      pidsDirty: false,
    })
  },

  async loadFromFc(protocol) {
    if (get().loading) return
    if (!protocol.downloadLogicConditions || !protocol.downloadProgrammingPids) {
      set({ error: 'Programming framework not supported by this firmware' })
      return
    }
    set({ loading: true, error: null })
    try {
      const [rawConditions, rawPids] = await Promise.all([
        protocol.downloadLogicConditions(),
        protocol.downloadProgrammingPids(),
      ])

      const conditions = defaultLogicConditions()
      rawConditions.forEach((c, i) => {
        if (i < LOGIC_CONDITION_MAX) conditions[i] = c
      })

      const pids = defaultProgrammingPids()
      rawPids.forEach((p, i) => {
        if (i < PROGRAMMING_PID_MAX) pids[i] = p
      })

      set({ conditions, pids, loading: false, conditionsDirty: false, pidsDirty: false })
    } catch (err) {
      set({ loading: false, error: formatErrorMessage(err) })
    }
  },

  async uploadConditions(protocol) {
    if (get().loading) return
    if (!protocol.uploadLogicCondition) {
      set({ error: 'Logic condition upload not supported' })
      return
    }
    set({ loading: true, error: null })
    try {
      const { conditions } = get()
      for (let i = 0; i < conditions.length; i++) {
        if (!get().loading) break
        await protocol.uploadLogicCondition(i, conditions[i])
      }
      set({ loading: false, conditionsDirty: false })
    } catch (err) {
      set({ loading: false, error: formatErrorMessage(err) })
    }
  },

  async uploadPids(protocol) {
    if (get().loading) return
    if (!protocol.uploadProgrammingPid) {
      set({ error: 'Programming PID upload not supported' })
      return
    }
    set({ loading: true, error: null })
    try {
      const { pids } = get()
      for (let i = 0; i < pids.length; i++) {
        if (!get().loading) break
        await protocol.uploadProgrammingPid(i, pids[i])
      }
      set({ loading: false, pidsDirty: false })
    } catch (err) {
      set({ loading: false, error: formatErrorMessage(err) })
    }
  },

  async writeGvar(protocol, index, value) {
    if (!protocol.setGvar) {
      set({ error: 'Global variable set not supported by this firmware' })
      return
    }
    set({ error: null })
    try {
      const res = await protocol.setGvar(index, value)
      if (!res.success) {
        set({ error: res.message })
        return
      }
      // reflect the newly-set value locally until the next status poll
      const values = [...get().gvarStatus.values]
      values[index] = value
      set({ gvarStatus: { values } })
    } catch (err) {
      set({ error: formatErrorMessage(err) })
    }
  },

  async pollStatus(protocol) {
    try {
      const results = await Promise.allSettled([
        protocol.downloadLogicConditionsStatus?.() ?? Promise.resolve([]),
        protocol.downloadGvarStatus?.() ?? Promise.resolve({ values: [] }),
        protocol.downloadProgrammingPidStatus?.() ?? Promise.resolve([]),
      ])

      const conditionsStatus =
        results[0].status === 'fulfilled' ? (results[0].value as INavLogicConditionsStatus[]) : get().conditionsStatus
      const gvarStatus =
        results[1].status === 'fulfilled' ? (results[1].value as INavGvarStatus) : get().gvarStatus
      const pidStatus =
        results[2].status === 'fulfilled' ? (results[2].value as INavProgrammingPidStatus[]) : get().pidStatus

      set({ conditionsStatus, gvarStatus, pidStatus })
    } catch {
      // status polling is best-effort
    }
  },

  startPolling(protocol, intervalMs = 500) {
    const existing = get().pollingTimer
    if (existing !== null) return
    const timer = setInterval(() => {
      get().pollStatus(protocol)
    }, intervalMs)
    set({ pollingTimer: timer })
  },

  stopPolling() {
    const timer = get().pollingTimer
    if (timer !== null) {
      clearInterval(timer)
      set({ pollingTimer: null })
    }
  },
}))
