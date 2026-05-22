import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, ChangeListItem } from './api'
import { ChangeDetail } from './ChangeDetail'

export function ReviewQueue() {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [reviewerName, setReviewerName] = useState(() => localStorage.getItem('reviewerName') ?? '')

  const { data: queue = [], isLoading } = useQuery({
    queryKey: ['review-queue'],
    queryFn: api.getQueue,
  })

  const handleReviewerNameChange = (name: string) => {
    setReviewerName(name)
    localStorage.setItem('reviewerName', name)
  }

  const statusDot = (status: string) => {
    if (status === 'summary_failed') return '🔴'
    if (status === 'in_review') return '🟡'
    return '🟢'
  }

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <div style={{ width: 360, borderRight: '1px solid #e5e7eb', overflowY: 'auto', padding: '1rem' }}>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="reviewer-name">Reviewer name</label>
          <input
            id="reviewer-name"
            value={reviewerName}
            onChange={e => handleReviewerNameChange(e.target.value)}
            placeholder="Your name"
          />
        </div>
        <h2>Review Queue</h2>
        {isLoading && <p>Loading...</p>}
        {queue.map((item: ChangeListItem) => (
          <div
            key={item.id}
            onClick={() => setSelectedId(item.id)}
            style={{
              padding: '0.75rem',
              cursor: 'pointer',
              background: selectedId === item.id ? '#f3f4f6' : undefined,
              borderBottom: '1px solid #e5e7eb',
            }}
            data-testid={`queue-row-${item.id}`}
          >
            <div>{statusDot(item.status)} <span data-testid="status-chip">{item.status}</span></div>
            <div data-testid="headline">{item.headline ?? '(no headline)'}</div>
            <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{item.source_layer}</div>
          </div>
        ))}
        {queue.length === 0 && !isLoading && <p>Queue empty.</p>}
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {selectedId ? (
          <ChangeDetail
            changeId={selectedId}
            reviewerName={reviewerName}
            onActionComplete={() => {
              setSelectedId(null)
            }}
          />
        ) : (
          <div style={{ padding: '2rem', color: '#9ca3af' }}>Select a change to review</div>
        )}
      </div>
    </div>
  )
}
