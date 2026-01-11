import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ticketApi } from '../services/api'
import { useAuthStore } from '../hooks/useAuth'
import type { Ticket } from '../types'

const priorityColors = {
  1: 'bg-health-100 dark:bg-health-900 text-health-800 dark:text-health-200',
  2: 'bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200',
  3: 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200',
  4: 'bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-200',
  5: 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200',
}

const statusColors = {
  open: 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200',
  assigned: 'bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200',
  in_progress: 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200',
  completed: 'bg-health-100 dark:bg-health-900 text-health-800 dark:text-health-200',
  cancelled: 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200',
}

export default function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>()
  const navigate = useNavigate()
  const { logout, user } = useAuthStore()
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [reviewNotes, setReviewNotes] = useState('')
  
  // Determine dashboard route based on user type
  const getDashboardRoute = () => {
    if (user?.type === 'patient') {
      return '/dashboard/patient'
    }
    return '/dashboard/service-person'
  }
  
  // Handle back navigation - go back in browser history, fallback to dashboard
  const handleBack = () => {
    // Try to go back in browser history first
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      // Fallback to dashboard route if no history
      navigate(getDashboardRoute())
    }
  }

  const loadTicket = useCallback(async () => {
    if (!ticketId) return
    try {
      setLoading(true)
      setError(null)
      const ticketData = await ticketApi.get(ticketId)
      setTicket(ticketData)
    } catch (err: any) {
      console.error('Failed to load ticket:', err)
      console.error('Error details:', {
        message: err.message,
        response: err.response,
        stack: err.stack
      })
      setError(err.response?.data?.detail || err.message || 'Failed to load ticket details')
    } finally {
      setLoading(false)
    }
  }, [ticketId])

  useEffect(() => {
    loadTicket()
  }, [loadTicket])

  const handleAcceptReject = async (action: 'accept' | 'reject') => {
    if (!ticketId || !ticket) return

    try {
      setActionLoading(true)
      const result = await ticketApi.acceptReject(ticketId, action)
      
      if (action === 'accept' && result.cancelled_tickets) {
        alert(`Ticket accepted! ${result.cancelled_tickets} other ticket(s) have been cancelled.`)
      } else if (action === 'reject') {
        alert('Ticket rejected successfully.')
      }
      
      // Reload ticket to get updated status
      await loadTicket()
      
      // Stay on ticket detail page - user can manually navigate back if needed
    } catch (err: any) {
      console.error('Failed to accept/reject ticket:', err)
      alert(err.response?.data?.detail || 'Failed to accept/reject ticket')
    } finally {
      setActionLoading(false)
    }
  }

  const handleUpdateStatus = async (status: string) => {
    if (!ticketId) return

    // For sequential review tickets, require review notes when completing
    if (ticket?.is_sequential_review && status === 'completed' && !reviewNotes.trim()) {
      alert('Please provide review notes before completing this sequential review ticket.')
      return
    }

    try {
      setActionLoading(true)
      await ticketApi.updateStatus(ticketId, status, ticket?.is_sequential_review ? reviewNotes : undefined)
      setReviewNotes('') // Clear review notes after submission
      await loadTicket()
    } catch (err: any) {
      console.error('Failed to update status:', err)
      alert(err.response?.data?.detail || 'Failed to update status')
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
          {error && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Please check the browser console for more details.
            </p>
          )}
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-teal-500 text-white rounded-md hover:bg-teal-600"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  // Safely parse patient_details - it might be a string (JSON) or object
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

  // Parse previous reviews from description for sequential reviews
  let previousReviews: string | null = null
  let currentCaseDescription: string = ticket.description || ''
  if (ticket.is_sequential_review && ticket.description) {
    const desc = typeof ticket.description === 'string' ? ticket.description : JSON.stringify(ticket.description)
    const previousReviewsMatch = desc.match(/PREVIOUS DOCTORS' REVIEWS:\n([\s\S]*?)\n\nCURRENT CASE:/)
    if (previousReviewsMatch) {
      previousReviews = previousReviewsMatch[1].trim()
      // Extract current case description
      const currentCaseMatch = desc.match(/CURRENT CASE:\n([\s\S]*?)\n\n\nSequential Review - Step/)
      if (currentCaseMatch) {
        currentCaseDescription = currentCaseMatch[1].trim()
      }
    } else {
      // If no previous reviews section, try to extract just the current case
      const currentCaseMatch = desc.match(/CURRENT CASE:\n([\s\S]*?)(?:\n\n\nSequential Review - Step|$)/)
      if (currentCaseMatch) {
        currentCaseDescription = currentCaseMatch[1].trim()
      }
    }
  }

  // Step information is now available via sequential_review_info

  return (
    <div className="min-h-screen bg-teal-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={handleBack}
                className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
              >
                ← Back
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Ticket Details</h1>
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
                    {ticket.service_type 
                      ? (typeof ticket.service_type === 'string' 
                          ? ticket.service_type.replace('_', ' ').toUpperCase() 
                          : String(ticket.service_type))
                      : 'Unknown Service'}
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Created: {ticket.created_at ? new Date(ticket.created_at).toLocaleString() : 'Unknown'}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {ticket.is_sequential_review && (
                    <span className="px-3 py-1 rounded-full text-sm font-medium bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200">
                      Sequential Review
                    </span>
                  )}
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${priorityColors[ticket.priority as keyof typeof priorityColors] || 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'}`}>
                    Priority {ticket.priority || 'N/A'}
                  </span>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusColors[ticket.status as keyof typeof statusColors] || 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'}`}>
                    {ticket.status 
                      ? (typeof ticket.status === 'string' 
                          ? ticket.status.replace('_', ' ') 
                          : String(ticket.status))
                      : 'Unknown'}
                  </span>
                </div>
              </div>

              {/* Previous Doctors' Reviews Section */}
              {ticket.is_sequential_review && previousReviews && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mb-4">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Previous Doctors' Reviews
                  </h3>
                  <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
                    <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap text-sm">
                      {previousReviews}
                    </p>
                  </div>
                </div>
              )}

              <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Current Case</h3>
                <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap">
                  {currentCaseDescription || 'No description provided'}
                </p>
                {ticket.is_sequential_review && ticket.sequential_review_info && (
                  <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg border border-blue-200 dark:border-blue-800">
                    <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                      Step {ticket.sequential_review_info.current_step_number} of {ticket.sequential_review_info.total_steps}
                    </p>
                    {ticket.sequential_review_info.steps[ticket.sequential_review_info.current_step_index] && (
                      <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
                        Currently with: {ticket.sequential_review_info.steps[ticket.sequential_review_info.current_step_index].doctor_name} ({ticket.sequential_review_info.steps[ticket.sequential_review_info.current_step_index].service_type})
                      </p>
                    )}
                    {ticket.sequential_review_info && ticket.sequential_review_info.current_step_number < ticket.sequential_review_info.total_steps && (
                      <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                        Next: {ticket.sequential_review_info.steps[ticket.sequential_review_info.current_step_index + 1]?.doctor_name || 'Pending'}
                      </p>
                    )}
                  </div>
                )}
              </div>
              
              {/* All Doctors Section - for regular requests with multiple tickets */}
              {ticket.all_doctors && ticket.all_doctors.length > 0 && !ticket.is_sequential_review && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                    All Doctors ({ticket.total_tickets || ticket.all_doctors.length} {ticket.total_tickets === 1 ? 'doctor' : 'doctors'} offered)
                  </h3>
                  <div className="space-y-2">
                    {ticket.all_doctors.map((doctor, idx) => (
                      <div
                        key={doctor.ticket_id}
                        className={`p-3 rounded-lg border ${
                          doctor.accepted
                            ? 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-800'
                            : doctor.status === 'cancelled' || doctor.assignment_status === 'rejected'
                            ? 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800'
                            : 'bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium text-gray-900 dark:text-gray-100">
                              {idx + 1}. {doctor.doctor_name}
                            </p>
                            <p className="text-xs text-gray-600 dark:text-gray-400">
                              {doctor.service_type}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {doctor.accepted && (
                              <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">
                                ✓ Accepted
                              </span>
                            )}
                            {!doctor.accepted && doctor.status === 'cancelled' && (
                              <span className="px-2 py-1 rounded text-xs font-medium bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200">
                                Rejected
                              </span>
                            )}
                            {!doctor.accepted && doctor.status !== 'cancelled' && (
                              <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200">
                                Pending
                              </span>
                            )}
                          </div>
                        </div>
                        {doctor.accepted && doctor.accepted_at && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            Accepted: {new Date(doctor.accepted_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {ticket.current_symptoms && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Current Symptoms</h3>
                  <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap">
                    {typeof ticket.current_symptoms === 'string' 
                      ? ticket.current_symptoms 
                      : JSON.stringify(ticket.current_symptoms)}
                  </p>
                </div>
              )}
            </div>

            {/* Patient Details Card */}
            {patientDetails && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Patient Details</h2>
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
                  {patientDetails.patient_id && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Patient ID</p>
                      <p className="text-gray-900 dark:text-gray-100 font-mono text-sm">{patientDetails.patient_id}</p>
                    </div>
                  )}
                  {patientDetails.blood_group && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Blood Group</p>
                      <p className="text-gray-900 dark:text-gray-100 font-semibold">{patientDetails.blood_group}</p>
                    </div>
                  )}
                  {patientDetails.age !== undefined && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Age</p>
                      <p className="text-gray-900 dark:text-gray-100">{patientDetails.age} years</p>
                    </div>
                  )}
                  {patientDetails.gender && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Gender</p>
                      <p className="text-gray-900 dark:text-gray-100">{patientDetails.gender}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Sequential Review Progress Card */}
            {ticket.is_sequential_review && ticket.sequential_review_info && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                  Sequential Review Progress ({ticket.sequential_review_info.current_step_number}/{ticket.sequential_review_info.total_steps})
                </h2>
                
                {/* Step Progress Indicator */}
                <div className="mb-6">
                  <div className="relative">
                    {/* Connection line */}
                    <div className="absolute top-5 left-10 right-10 h-0.5 bg-gray-300 dark:bg-gray-600 z-0" />
                    {/* Completed steps line - calculate based on number of completed steps */}
                    {(() => {
                      const completedSteps = ticket.sequential_review_info.steps.filter(step => step.status === 'completed').length;
                      const totalSteps = ticket.sequential_review_info.steps.length;
                      // Only show green line if there are completed steps and more than 1 step total
                      if (completedSteps > 0 && totalSteps > 1) {
                        // Calculate width: (completedSteps / (totalSteps - 1)) gives progress between steps
                        // If all steps are completed, width should be 100%
                        const progressRatio = totalSteps > 1 ? (completedSteps / (totalSteps - 1)) : 1;
                        const widthPercent = Math.min(progressRatio * 100, 100);
                        return (
                          <div 
                            className="absolute top-5 left-10 h-0.5 bg-green-500 z-0"
                            style={{ 
                              width: `calc(${widthPercent}% - 40px)`
                            }}
                          />
                        );
                      }
                      return null;
                    })()}
                    
                    <div className="flex items-start justify-between relative z-10">
                      {ticket.sequential_review_info.steps.map((step) => (
                        <div key={step.step_id} className="flex-1 flex flex-col items-center">
                          <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                            step.status === 'completed' 
                              ? 'bg-green-500 text-white' 
                              : step.status === 'in_review' 
                              ? 'bg-yellow-500 text-white' 
                              : step.step_index === ticket.sequential_review_info!.current_step_index && ticket.status === 'assigned'
                              ? 'bg-blue-500 text-white'
                              : 'bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                          }`}>
                            {step.step_number}
                          </div>
                          <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 text-center max-w-[100px] truncate">
                            {step.doctor_name}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1 text-center">
                            {step.status === 'completed' ? 'Done' : 
                             step.status === 'in_review' ? 'In Progress' :
                             step.step_index === ticket.sequential_review_info!.current_step_index && ticket.status === 'assigned' ? 'Ready' :
                             'Pending'}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                
                {/* Previous Steps' Review Notes */}
                {ticket.sequential_review_info.steps.filter(step => step.status === 'completed' && step.review_notes).length > 0 && (
                  <div className="mt-6 space-y-4">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Previous Reviews</h3>
                    {ticket.sequential_review_info.steps
                      .filter(step => step.status === 'completed' && step.review_notes)
                      .map(step => (
                        <div key={step.step_id} className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="font-medium text-gray-900 dark:text-white">
                              Step {step.step_number}: {step.doctor_name} ({step.service_type})
                            </h4>
                            {step.completed_at && (
                              <p className="text-xs text-gray-600 dark:text-gray-400">
                                {new Date(step.completed_at).toLocaleDateString()}
                              </p>
                            )}
                          </div>
                          {step.review_summary && (
                            <p className="text-sm text-gray-700 dark:text-gray-300 mb-2 italic">
                              Summary: {step.review_summary}
                            </p>
                          )}
                          <p className="text-sm text-gray-900 dark:text-gray-100 whitespace-pre-wrap">
                            {step.review_notes}
                          </p>
                        </div>
                      ))}
                  </div>
                )}
                
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-4">
                  This is a multi-doctor sequential review. Your review notes will be shared with the next doctor in the chain.
                </p>
              </div>
            )}

            {/* LLM Summary Card (for non-sequential reviews) */}
            {!ticket.is_sequential_review && ticket.llm_summary && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">AI Summary</h2>
                <div className="bg-teal-50 dark:bg-teal-900/30 rounded-lg p-4 border border-teal-200 dark:border-teal-800">
                  <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap text-sm">
                    {ticket.llm_summary}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Actions */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 sticky top-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Actions</h3>
              
              {/* Accept/Reject Buttons - Only for service persons, hidden for sequential review tickets */}
              {user?.type === 'service_person' && ticket.status === 'open' && !ticket.is_sequential_review && (
                <div className="space-y-3">
                  <button
                    onClick={() => handleAcceptReject('accept')}
                    disabled={actionLoading}
                    className="w-full px-4 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {actionLoading ? 'Processing...' : 'Accept Ticket'}
                  </button>
                  <button
                    onClick={() => handleAcceptReject('reject')}
                    disabled={actionLoading}
                    className="w-full px-4 py-3 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {actionLoading ? 'Processing...' : 'Reject Ticket'}
                  </button>
                  <p className="text-xs text-gray-500 dark:text-gray-400 text-center mt-2">
                    Accepting will automatically cancel tickets for other doctors in this recommendation
                  </p>
                </div>
              )}
              
              {/* Sequential Review Info - Only for service persons */}
              {user?.type === 'service_person' && ticket.is_sequential_review && ticket.status === 'assigned' && (
                <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg border border-blue-200 dark:border-blue-800">
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    This ticket is automatically assigned to you. Click "Start Work" to begin your review.
                  </p>
                </div>
              )}

              {/* Status Update Buttons - Only for service persons */}
              {user?.type === 'service_person' && ticket.status === 'assigned' && (
                <button
                  onClick={() => handleUpdateStatus('in_progress')}
                  disabled={actionLoading}
                  className="w-full px-4 py-3 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {actionLoading ? 'Processing...' : 'Start Work'}
                </button>
              )}

              {user?.type === 'service_person' && ticket.status === 'in_progress' && (
                <div className="space-y-3">
                  {ticket.is_sequential_review && (
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
                  )}
                  <button
                    onClick={() => handleUpdateStatus('completed')}
                    disabled={actionLoading || (ticket.is_sequential_review && !reviewNotes.trim())}
                    className="w-full px-4 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {actionLoading ? 'Processing...' : 'Mark as Completed'}
                  </button>
                </div>
              )}

              {/* Ticket Info */}
              <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Ticket Information</h4>
                <div className="space-y-2 text-sm">
                  <div>
                    <p className="text-gray-600 dark:text-gray-400">Service Type</p>
                    <p className="text-gray-900 dark:text-gray-100 font-medium">{ticket.service_type}</p>
                  </div>
                  <div>
                    <p className="text-gray-600 dark:text-gray-400">Priority</p>
                    <p className="text-gray-900 dark:text-gray-100 font-medium">Level {ticket.priority}</p>
                  </div>
                  {ticket.assigned_at && (
                    <div>
                      <p className="text-gray-600 dark:text-gray-400">Assigned At</p>
                      <p className="text-gray-900 dark:text-gray-100 font-medium">
                        {ticket.assigned_at ? new Date(ticket.assigned_at).toLocaleString() : 'Unknown'}
                      </p>
                    </div>
                  )}
                  {ticket.completed_at && (
                    <div>
                      <p className="text-gray-600 dark:text-gray-400">Completed At</p>
                      <p className="text-gray-900 dark:text-gray-100 font-medium">
                        {ticket.completed_at ? new Date(ticket.completed_at).toLocaleString() : 'Unknown'}
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
