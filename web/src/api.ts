const API_KEY = import.meta.env.VITE_API_KEY ?? ''

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export interface ChangeListItem {
  id: number
  source_layer: string
  headline: string | null
  status: string
  detected_at: string
  updated_at: string
  summary_error?: string | null
}

export interface ChangeSummary {
  headline: string
  what_changed: string
  where: string
  to_whom: string
  for_what_cases: string
}

export interface ChangeDetail {
  id: number
  source_layer: string
  source_url: string
  headline: string | null
  status: string
  detected_at: string
  updated_at: string
  effective_date: string | null
  summary: ChangeSummary | null
  diff_text: string | null
  not_legal_advice_label: string | null
  summary_error?: string | null
}

export const api = {
  getQueue: () => apiFetch<ChangeListItem[]>('/review/queue'),
  getChange: (id: number) => apiFetch<ChangeDetail>(`/review/${id}`),
  approve: (id: number, effective_date: string, reviewer_name: string) =>
    apiFetch<ChangeDetail>(`/review/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ effective_date, reviewer_name }),
    }),
  edit: (id: number, summary: ChangeSummary, reviewer_name: string) =>
    apiFetch<ChangeDetail>(`/review/${id}/edit`, {
      method: 'POST',
      body: JSON.stringify({ summary, reviewer_name }),
    }),
  reject: (id: number, reviewer_name: string) =>
    apiFetch<ChangeDetail>(`/review/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_name }),
    }),
  retrySummary: (id: number) =>
    apiFetch<ChangeDetail>(`/review/${id}/retry-summary`, { method: 'POST' }),
}
