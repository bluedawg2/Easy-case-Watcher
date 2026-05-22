import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import ReactDiffViewer from 'react-diff-viewer-continued'
import { api, ChangeSummary } from './api'

const NOT_LEGAL_ADVICE = 'Informational summary — not legal advice.'

interface Props {
  changeId: number
  reviewerName: string
  onActionComplete: () => void
}

export function ChangeDetail({ changeId, reviewerName, onActionComplete }: Props) {
  const queryClient = useQueryClient()
  const [effectiveDate, setEffectiveDate] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [editedSummary, setEditedSummary] = useState<ChangeSummary | null>(null)

  const { data: change, isLoading } = useQuery({
    queryKey: ['change', changeId],
    queryFn: () => api.getChange(changeId),
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['review-queue'] })
    queryClient.invalidateQueries({ queryKey: ['change', changeId] })
  }

  const approveMutation = useMutation({
    mutationFn: () => api.approve(changeId, effectiveDate, reviewerName),
    onSuccess: () => { invalidate(); onActionComplete() },
  })

  const editMutation = useMutation({
    mutationFn: () => api.edit(changeId, editedSummary!, reviewerName),
    onSuccess: () => { invalidate(); setEditMode(false) },
  })

  const rejectMutation = useMutation({
    mutationFn: () => api.reject(changeId, reviewerName),
    onSuccess: () => { invalidate(); onActionComplete() },
  })

  const retryMutation = useMutation({
    mutationFn: () => api.retrySummary(changeId),
    onSuccess: () => invalidate(),
  })

  if (isLoading || !change) return <div style={{ padding: '2rem' }}>Loading...</div>

  const isSummaryFailed = change.status === 'summary_failed'

  return (
    <div style={{ padding: '2rem' }}>
      <h2>{change.headline ?? '(no headline)'}</h2>
      <p style={{ fontStyle: 'italic', color: '#6b7280' }} data-testid="not-legal-advice">
        {NOT_LEGAL_ADVICE}
      </p>

      {isSummaryFailed ? (
        <div>
          <p style={{ color: '#ef4444' }}>Summary failed: {change.summary_error}</p>
          <button onClick={() => retryMutation.mutate()} data-testid="retry-summary-btn">
            Retry summary
          </button>
        </div>
      ) : (
        <>
          {change.summary && !editMode && (
            <details>
              <summary>Structured summary</summary>
              <dl>
                <dt>What changed</dt><dd>{change.summary.what_changed}</dd>
                <dt>Where</dt><dd>{change.summary.where}</dd>
                <dt>To whom</dt><dd>{change.summary.to_whom}</dd>
                <dt>For what cases</dt><dd>{change.summary.for_what_cases}</dd>
              </dl>
            </details>
          )}
          {editMode && editedSummary && (
            <div>
              {(['headline', 'what_changed', 'where', 'to_whom', 'for_what_cases'] as const).map(f => (
                <div key={f}>
                  <label>{f}</label>
                  {f === 'headline'
                    ? <input value={editedSummary[f]} onChange={e => setEditedSummary({ ...editedSummary, [f]: e.target.value })} />
                    : <textarea value={editedSummary[f]} onChange={e => setEditedSummary({ ...editedSummary, [f]: e.target.value })} />
                  }
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {change.diff_text && (
        <div data-testid="diff-viewer">
          <ReactDiffViewer
            oldValue={change.diff_text}
            newValue={change.diff_text}
            splitView={false}
          />
        </div>
      )}

      <div>
        <a href={change.source_url} target="_blank" rel="noopener noreferrer">View source</a>
      </div>

      {!isSummaryFailed && (
        <div data-testid="action-row" style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input
            type="date"
            value={effectiveDate}
            onChange={e => setEffectiveDate(e.target.value)}
            data-testid="effective-date-input"
          />
          <button
            onClick={() => approveMutation.mutate()}
            disabled={!effectiveDate}
            data-testid="approve-btn"
          >
            Approve
          </button>
          <button
            data-testid="edit-btn"
            onClick={() => {
              if (!editMode) {
                setEditedSummary(change.summary as ChangeSummary ?? { headline: '', what_changed: '', where: '', to_whom: '', for_what_cases: '' })
                setEditMode(true)
              } else {
                editMutation.mutate()
              }
            }}
          >
            {editMode ? 'Save edit' : 'Edit summary'}
          </button>
          <button onClick={() => rejectMutation.mutate()} data-testid="reject-btn">
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
