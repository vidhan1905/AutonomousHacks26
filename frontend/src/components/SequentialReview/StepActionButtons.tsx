import { useState } from 'react'
import type { SequentialReviewTicket } from '../../types'

interface StepActionButtonsProps {
  ticket: SequentialReviewTicket
  onAccept: () => Promise<void>
  onReject: () => Promise<void>
  onStartWork: () => Promise<void>
  onComplete: (reviewNotes: string) => Promise<void>
  loading?: boolean
}

export default function StepActionButtons({
  ticket,
  onAccept,
  onReject,
  onStartWork,
  onComplete,
  loading = false,
}: StepActionButtonsProps) {
  const [reviewNotes, setReviewNotes] = useState('')

  const handleComplete = async () => {
    if (!reviewNotes.trim()) {
      alert('Please provide review notes before completing this step.')
      return
    }
    await onComplete(reviewNotes)
    setReviewNotes('') // Clear after submission
  }

  return (
    <div className="space-y-3">
      {/* Waiting message - shown when step is pending but can_start is false */}
      {ticket.status === 'step_pending' && !ticket.can_start && (
        <div className="bg-yellow-50 dark:bg-yellow-900/30 rounded-lg p-4 border border-yellow-200 dark:border-yellow-800">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            ⏳ Waiting for previous doctor to complete their review...
          </p>
          <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">
            Step {ticket.step_index + 1} will be available once the previous step is completed.
          </p>
        </div>
      )}

      {/* Accept/Reject Buttons - shown when step is pending and can_start is true */}
      {ticket.status === 'step_pending' && ticket.can_start && (
        <>
          <button
            onClick={onAccept}
            disabled={loading}
            className="w-full px-4 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Processing...' : 'Accept Step'}
          </button>
          <button
            onClick={onReject}
            disabled={loading}
            className="w-full px-4 py-3 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Processing...' : 'Reject Step'}
          </button>
        </>
      )}

      {/* Start Work Button - shown when step is accepted */}
      {ticket.status === 'step_accepted' && (
        <button
          onClick={onStartWork}
          disabled={loading}
          className="w-full px-4 py-3 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Processing...' : 'Start Work'}
        </button>
      )}

      {/* Complete Button - shown when step is in progress */}
      {ticket.status === 'step_in_progress' && (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Review Notes <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
              placeholder="Enter your review notes, findings, and recommendations. This will be shared with the next doctor in the sequential review chain."
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Required for sequential review tickets
            </p>
          </div>
          <button
            onClick={handleComplete}
            disabled={loading || !reviewNotes.trim()}
            className="w-full px-4 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Processing...' : 'Complete Step'}
          </button>
        </div>
      )}

      {/* Status messages */}
      {ticket.status === 'step_completed' && (
        <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            Step completed. Waiting for next step in the chain.
          </p>
        </div>
      )}

      {ticket.status === 'chain_completed' && (
        <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-4 border border-green-200 dark:border-green-800">
          <p className="text-sm text-green-800 dark:text-green-200">
            All steps completed. Sequential review chain finished.
          </p>
        </div>
      )}

      {ticket.status === 'chain_cancelled' && (
        <div className="bg-red-50 dark:bg-red-900/30 rounded-lg p-4 border border-red-200 dark:border-red-800">
          <p className="text-sm text-red-800 dark:text-red-200">
            Sequential review chain has been cancelled.
          </p>
        </div>
      )}
    </div>
  )
}
