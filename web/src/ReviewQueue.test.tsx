import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReviewQueue } from './ReviewQueue'

// Mock the api module
vi.mock('./api', () => ({
  api: {
    getQueue: vi.fn(),
    getChange: vi.fn(),
    approve: vi.fn(),
    edit: vi.fn(),
    reject: vi.fn(),
    retrySummary: vi.fn(),
  },
}))

import { api } from './api'

const mockQueueItem = {
  id: 1,
  source_layer: 'FRBP',
  headline: 'Test rule change',
  status: 'processed',
  detected_at: '2026-05-22T10:00:00Z',
  updated_at: '2026-05-22T10:00:00Z',
}

const mockChangeDetail = {
  id: 1,
  source_layer: 'FRBP',
  source_url: 'https://example.com',
  headline: 'Test rule change',
  status: 'processed',
  detected_at: '2026-05-22T10:00:00Z',
  updated_at: '2026-05-22T10:00:00Z',
  effective_date: null,
  summary: {
    headline: 'Test rule change',
    what_changed: 'Rule changed',
    where: 'Rule 1007',
    to_whom: 'Debtors',
    for_what_cases: 'Chapter 7',
  },
  diff_text: '-old\n+new\n',
  not_legal_advice_label: 'Informational summary — not legal advice.',
}

const mockSummaryFailedItem = {
  id: 2,
  source_layer: 'FRBP',
  headline: null,
  status: 'summary_failed',
  detected_at: '2026-05-22T10:00:00Z',
  updated_at: '2026-05-22T10:00:00Z',
  summary_error: 'API timeout',
}

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('ReviewQueue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows queue rows with headline and status', async () => {
    vi.mocked(api.getQueue).mockResolvedValue([mockQueueItem])
    renderWithQuery(<ReviewQueue />)
    await waitFor(() => {
      expect(screen.getByTestId('headline')).toHaveTextContent('Test rule change')
      expect(screen.getByTestId('status-chip')).toHaveTextContent('processed')
    })
  })

  it('renders ChangeDetail when a row is selected', async () => {
    vi.mocked(api.getQueue).mockResolvedValue([mockQueueItem])
    vi.mocked(api.getChange).mockResolvedValue(mockChangeDetail)
    renderWithQuery(<ReviewQueue />)
    await waitFor(() => screen.getByTestId('queue-row-1'))
    fireEvent.click(screen.getByTestId('queue-row-1'))
    await waitFor(() => {
      expect(screen.getByTestId('not-legal-advice')).toBeInTheDocument()
    })
  })

  it('approve button is disabled without effective date, enabled with date', async () => {
    vi.mocked(api.getQueue).mockResolvedValue([mockQueueItem])
    vi.mocked(api.getChange).mockResolvedValue(mockChangeDetail)
    renderWithQuery(<ReviewQueue />)
    await waitFor(() => screen.getByTestId('queue-row-1'))
    fireEvent.click(screen.getByTestId('queue-row-1'))
    await waitFor(() => screen.getByTestId('approve-btn'))
    expect(screen.getByTestId('approve-btn')).toBeDisabled()
    fireEvent.change(screen.getByTestId('effective-date-input'), { target: { value: '2026-12-01' } })
    expect(screen.getByTestId('approve-btn')).not.toBeDisabled()
  })

  it('summary_failed change renders Retry summary action', async () => {
    vi.mocked(api.getQueue).mockResolvedValue([mockSummaryFailedItem])
    vi.mocked(api.getChange).mockResolvedValue({
      ...mockChangeDetail,
      id: 2,
      status: 'summary_failed',
      summary: null,
      headline: null,
      summary_error: 'API timeout',
    })
    renderWithQuery(<ReviewQueue />)
    await waitFor(() => screen.getByTestId('queue-row-2'))
    fireEvent.click(screen.getByTestId('queue-row-2'))
    await waitFor(() => screen.getByTestId('retry-summary-btn'))
    expect(screen.getByTestId('retry-summary-btn')).toBeInTheDocument()
    // approve/edit/reject should NOT appear
    expect(screen.queryByTestId('approve-btn')).not.toBeInTheDocument()
  })
})
