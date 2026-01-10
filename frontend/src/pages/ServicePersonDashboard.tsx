import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../hooks/useAuth'
import TicketDashboard from '../components/Dashboard/TicketDashboard'
import type { Ticket } from '../types'
import { ticketApi } from '../services/api'

export default function ServicePersonDashboard() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null)

  const handleViewTicket = async (ticketId: string) => {
    try {
      const ticket = await ticketApi.get(ticketId)
      setSelectedTicket(ticket)
    } catch (error) {
      console.error('Failed to load ticket:', error)
    }
  }

  const handleAssignToMe = async (ticketId: string) => {
    if (!user?.id) return
    try {
      await ticketApi.assign(ticketId, user.id)
      // Reload tickets
      window.location.reload()
    } catch (error) {
      console.error('Failed to assign ticket:', error)
    }
  }

  const handleUpdateStatus = async (ticketId: string, status: string) => {
    try {
      await ticketApi.updateStatus(ticketId, status)
      if (selectedTicket?.ticket_id === ticketId) {
        setSelectedTicket({ ...selectedTicket, status })
      }
      // Reload tickets
      window.location.reload()
    } catch (error) {
      console.error('Failed to update status:', error)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Service Person Dashboard</h1>
              <p className="text-sm text-gray-600">
                Welcome, {user?.name || user?.username} - {user?.service_type?.replace('_', ' ')}
              </p>
            </div>
            <button
              onClick={async () => {
                await logout()
                navigate('/login')
              }}
              className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Tickets</h2>
            <TicketDashboard userType="service_person" />
          </div>

          {selectedTicket && (
            <div className="lg:col-span-1">
              <div className="bg-white rounded-lg shadow-md p-6 sticky top-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Ticket Details</h3>
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-medium text-gray-700">Service Type</p>
                    <p className="text-sm text-gray-900">{selectedTicket.service_type}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700">Status</p>
                    <p className="text-sm text-gray-900">{selectedTicket.status}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700">Priority</p>
                    <p className="text-sm text-gray-900">{selectedTicket.priority}</p>
                  </div>
                  {selectedTicket.llm_summary && (
                    <div>
                      <p className="text-sm font-medium text-gray-700">LLM Summary</p>
                      <p className="text-sm text-gray-900 whitespace-pre-wrap">{selectedTicket.llm_summary}</p>
                    </div>
                  )}
                  {selectedTicket.patient_details && (
                    <div>
                      <p className="text-sm font-medium text-gray-700">Patient Details</p>
                      <pre className="text-xs text-gray-900 bg-gray-50 p-2 rounded overflow-auto">
                        {JSON.stringify(selectedTicket.patient_details, null, 2)}
                      </pre>
                    </div>
                  )}
                  <div className="flex space-x-2">
                    {selectedTicket.status === 'open' && (
                      <button
                        onClick={() => handleAssignToMe(selectedTicket.ticket_id)}
                        className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm"
                      >
                        Assign to Me
                      </button>
                    )}
                    {selectedTicket.status === 'assigned' && (
                      <button
                        onClick={() => handleUpdateStatus(selectedTicket.ticket_id, 'in_progress')}
                        className="flex-1 px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 text-sm"
                      >
                        Start Work
                      </button>
                    )}
                    {selectedTicket.status === 'in_progress' && (
                      <button
                        onClick={() => handleUpdateStatus(selectedTicket.ticket_id, 'completed')}
                        className="flex-1 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
                      >
                        Complete
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
