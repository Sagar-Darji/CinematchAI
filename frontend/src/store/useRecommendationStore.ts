import { create } from 'zustand'
import type { Recommendation, JobStatus } from '@/lib/api'

interface RecommendationState {
  recommendations: Recommendation[]
  jobId: string | null
  jobStatus: JobStatus['status'] | null
  steps: JobStatus['steps']
  isPolling: boolean
  traceId: string | null
  contextFactors: Record<string, string>

  setRecommendations: (recs: Recommendation[]) => void
  setJobId: (id: string | null) => void
  setJobStatus: (s: JobStatus['status'] | null) => void
  setSteps: (steps: JobStatus['steps']) => void
  setIsPolling: (v: boolean) => void
  setTraceId: (id: string | null) => void
  setContextFactors: (cf: Record<string, string>) => void
  reset: () => void
}

export const useRecommendationStore = create<RecommendationState>()((set) => ({
  recommendations: [],
  jobId: null,
  jobStatus: null,
  steps: [],
  isPolling: false,
  traceId: null,
  contextFactors: {},

  setRecommendations: (recs) => set({ recommendations: recs }),
  setJobId: (id) => set({ jobId: id }),
  setJobStatus: (s) => set({ jobStatus: s }),
  setSteps: (steps) => set({ steps }),
  setIsPolling: (v) => set({ isPolling: v }),
  setTraceId: (id) => set({ traceId: id }),
  setContextFactors: (cf) => set({ contextFactors: cf }),
  reset: () =>
    set({
      recommendations: [],
      jobId: null,
      jobStatus: null,
      steps: [],
      isPolling: false,
      traceId: null,
      contextFactors: {},
    }),
}))
