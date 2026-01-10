import { useState, useEffect } from 'react'
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
  const { logout } = useAuthStore()
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    if (ticketId) {
      loadTicket()
    }
  }, [ticketId])

  const loadTicket = async () => {
    try {
      setLoading(true)
      setError(null)
      const ticketData = await ticketApi.get(ticketId!)
      setTicket(ticketData)
    } catch (err: any) {
      console.error('Failed to load ticket:', err)
      setError(err.response?.data?.detail || 'Failed to load ticket details')
    } finally {
      setLoading(false)
    }
  }

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
      
      // Navigate back to dashboard after a short delay
      setTimeout(() => {
        navigate('/dashboard/service-person')
      }, 1500)
    } catch (err: any) {
      console.error('Failed to accept/reject ticket:', err)
      alert(err.response?.data?.detail || 'Failed to accept/reject ticket')
    } finally {
      setActionLoading(false)
    }
  }

  const handleUpdateStatus = async (status: string) => {
    if (!ticketId) return

    try {
      setActionLoading(true)
      await ticketApi.updateStatus(ticketId, status)
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

  const patientDetails = ticket.patient_details as any

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
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Ticket Details</h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Ticket ID: {ticket.ticket_id.substring(0, 8)}...
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
                    {ticket.service_type.replace('_', ' ').toUpperCase()}
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Created: {new Date(ticket.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex space-x-2">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${priorityColors[ticket.priority as keyof typeof priorityColors]}`}>
                    Priority {ticket.priority}
                  </span>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusColors[ticket.status as keyof typeof statusColors]}`}>
                    {ticket.status.replace('_', ' ')}
                  </span>
                </div>
              </div>

              <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Description</h3>
                <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap">{ticket.description}</p>
              </div>

              {ticket.current_symptoms && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Current Symptoms</h3>
                  <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap">{ticket.current_symptoms}</p>
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

            {/* LLM Summary Card */}
            {ticket.llm_summary && (
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
              
              {/* Accept/Reject Buttons */}
              {ticket.status === 'open' && (
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

              {/* Status Update Buttons */}
              {ticket.status === 'assigned' && (
                <button
                  onClick={() => handleUpdateStatus('in_progress')}
                  disabled={actionLoading}
                  className="w-full px-4 py-3 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {actionLoading ? 'Processing...' : 'Start Work'}
                </button>
              )}

              {ticket.status === 'in_progress' && (
                <button
                  onClick={() => handleUpdateStatus('completed')}
                  disabled={actionLoading}
                  className="w-full px-4 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {actionLoading ? 'Processing...' : 'Mark as Completed'}
                </button>
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
                        {new Date(ticket.assigned_at).toLocaleString()}
                      </p>
                    </div>
                  )}
                  {ticket.completed_at && (
                    <div>
                      <p className="text-gray-600 dark:text-gray-400">Completed At</p>
                      <p className="text-gray-900 dark:text-gray-100 font-medium">
                        {new Date(ticket.completed_at).toLocaleString()}
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
