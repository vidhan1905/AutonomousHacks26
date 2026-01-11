import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { sequentialReviewTicketApi } from '../services/api'
import { useAuthStore } from '../hooks/useAuth'
import type { SequentialReviewTicket } from '../types'
import StepProgressIndicator from '../components/SequentialReview/StepProgressIndicator'
import StepActionButtons from '../components/SequentialReview/StepActionButtons'
import PreviousReviewsCard from '../components/SequentialReview/PreviousReviewsCard'
import StepStatusBadge from '../components/SequentialReview/StepStatusBadge'

export default function SequentialReviewTicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>()
  const navigate = useNavigate()
  const { logout } = useAuthStore()
  const [ticket, setTicket] = useState<SequentialReviewTicket | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [progress, setProgress] = useState<any>(null)

  const loadTicket = useCallback(async () => {
    if (!ticketId) return
    try {
      setLoading(true)
      setError(null)
      const ticketData = await sequentialReviewTicketApi.get(ticketId)
      setTicket(ticketData)
      
      // Load progress
      try {
        const progressData = await sequentialReviewTicketApi.getProgress(ticketId)
        setProgress(progressData)
      } catch (err: any) {
        console.error('Failed to load progress:', err)
      }
    } catch (err: any) {
      console.error('Failed to load ticket:', err)
      setError(err.response?.data?.detail || err.message || 'Failed to load ticket details')
    } finally {
      setLoading(false)
    }
  }, [ticketId])

  useEffect(() => {
    loadTicket()
  }, [loadTicket])

  const handleAccept = async () => {
    if (!ticketId) return
    try {
      setActionLoading(true)
      await sequentialReviewTicketApi.acceptStep(ticketId)
      await loadTicket()
    } catch (err: any) {
      console.error('Failed to accept step:', err)
      alert(err.response?.data?.detail || 'Failed to accept step')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!ticketId) return
    if (!confirm('Are you sure you want to reject this step? This may cancel the entire chain.')) {
      return
    }
    try {
      setActionLoading(true)
      await sequentialReviewTicketApi.rejectStep(ticketId)
      await loadTicket()
    } catch (err: any) {
      console.error('Failed to reject step:', err)
      alert(err.response?.data?.detail || 'Failed to reject step')
    } finally {
      setActionLoading(false)
    }
  }

  const handleStartWork = async () => {
    if (!ticketId) return
    try {
      setActionLoading(true)
      await sequentialReviewTicketApi.updateStepStatus(ticketId, 'step_in_progress')
      await loadTicket()
    } catch (err: any) {
      console.error('Failed to start work:', err)
      alert(err.response?.data?.detail || 'Failed to start work')
    } finally {
      setActionLoading(false)
    }
  }

  const handleComplete = async (reviewNotes: string) => {
    if (!ticketId) return
    try {
      setActionLoading(true)
      await sequentialReviewTicketApi.updateStepStatus(ticketId, 'step_completed', reviewNotes)
      await loadTicket()
    } catch (err: any) {
      console.error('Failed to complete step:', err)
      alert(err.response?.data?.detail || 'Failed to complete step')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-teal-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-500 dark:border-teal-400 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Loading ticket details...</p>
        </div>
      </div>
    )
  }

  if (error || !ticket) {
    return (
      <div className="min-h-screen bg-teal-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400 mb-4">{error || 'Ticket not found'}</p>
          <button
            onClick={() => navigate('/dashboard/service-person')}
            className="px-4 py-2 bg-teal-500 text-white rounded-md hover:bg-teal-600"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  // Parse previous reviews from description
  let previousReviews: string | null = null
  let currentCaseDescription: string = ticket.description || ''
  if (ticket.description) {
    const desc = typeof ticket.description === 'string' ? ticket.description : JSON.stringify(ticket.description)
    const previousReviewsMatch = desc.match(/PREVIOUS DOCTORS' REVIEWS:\n([\s\S]*?)\n\nCURRENT CASE:/)
    if (previousReviewsMatch) {
      previousReviews = previousReviewsMatch[1].trim()
      const currentCaseMatch = desc.match(/CURRENT CASE:\n([\s\S]*?)\n\n\nSequential Review - Step/)
      if (currentCaseMatch) {
        currentCaseDescription = currentCaseMatch[1].trim()
      }
    } else {
      const currentCaseMatch = desc.match(/CURRENT CASE:\n([\s\S]*?)(?:\n\n\nSequential Review - Step|$)/)
      if (currentCaseMatch) {
        currentCaseDescription = currentCaseMatch[1].trim()
      }
    }
  }

  // Safely parse patient_details
  let patientDetails: any = null
  try {
    if (ticket.patient_details) {
      if (typeof ticket.patient_details === 'string') {
        patientDetails = JSON.parse(ticket.patient_details)
      } else {
        patientDetails = ticket.patient_details
      }
    }
  } catch (e) {
    console.error('Error parsing patient_details:', e)
    patientDetails = null
  }

  return (
    <div className="min-h-screen bg-teal-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => navigate('/dashboard/service-person')}
                className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
              >
                ← Back
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  Sequential Review Ticket
                </h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Ticket ID: {ticket.ticket_id ? `${ticket.ticket_id.substring(0, 8)}...` : 'N/A'}
                </p>
              </div>
            </div>
            <button
              onClick={async () => {
                await logout()
                navigate('/login')
              }}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Main Details */}
          <div className="lg:col-span-2 space-y-6">
            {/* Ticket Status Card */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                    Sequential Review Case
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Created: {ticket.created_at ? new Date(ticket.created_at).toLocaleString() : 'Unknown'}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StepStatusBadge status={ticket.status} />
                </div>
              </div>

              {/* Previous Reviews */}
              {previousReviews && (
                <div className="mb-4">
                  <PreviousReviewsCard previousReviews={previousReviews} />
                </div>
              )}

              {/* Current Case */}
              <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Current Case
                </h3>
                <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap">
                  {currentCaseDescription || 'No description provided'}
                </p>
              </div>
            </div>

            {/* Patient Details Card */}
            {patientDetails && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                  Patient Details
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {patientDetails.name && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Name</p>
                      <p className="text-gray-900 dark:text-gray-100">{patientDetails.name}</p>
                    </div>
                  )}
                  {patientDetails.phone && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Phone</p>
                      <p className="text-gray-900 dark:text-gray-100">{patientDetails.phone}</p>
                    </div>
                  )}
                  {patientDetails.date_of_birth && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Date of Birth
                      </p>
                      <p className="text-gray-900 dark:text-gray-100">
                        {patientDetails.date_of_birth}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Progress Indicator */}
            {progress && (
              <StepProgressIndicator ticket={ticket} progress={progress} />
            )}
          </div>

          {/* Right Column - Actions */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 sticky top-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Step Actions
              </h3>
              
              <StepActionButtons
                ticket={ticket}
                onAccept={handleAccept}
                onReject={handleReject}
                onStartWork={handleStartWork}
                onComplete={handleComplete}
                loading={actionLoading}
              />

              {/* Ticket Info */}
              <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Ticket Information
                </h4>
                <div className="space-y-2 text-sm">
                  <div>
                    <p className="text-gray-600 dark:text-gray-400">Chain ID</p>
                    <p className="text-gray-900 dark:text-gray-100 font-mono text-xs">
                      {ticket.chain_id.substring(0, 8)}...
                    </p>
                  </div>
                  {ticket.current_step && (
                    <div>
                      <p className="text-gray-600 dark:text-gray-400">Current Step</p>
                      <p className="text-gray-900 dark:text-gray-100 font-medium">
                        Step {ticket.current_step.step_index + 1} - {ticket.current_step.doctor_name}
                      </p>
                    </div>
                  )}
                  {ticket.chain_completed_at && (
                    <div>
                      <p className="text-gray-600 dark:text-gray-400">Completed At</p>
                      <p className="text-gray-900 dark:text-gray-100 font-medium">
                        {new Date(ticket.chain_completed_at).toLocaleString()}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
