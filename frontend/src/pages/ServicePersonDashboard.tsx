import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../hooks/useAuth'
import TicketDashboard from '../components/Dashboard/TicketDashboard'
import type { Ticket } from '../types'

export default function ServicePersonDashboard() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

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
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Your Tickets</h2>
          <TicketDashboard 
            userType="service_person" 
            onTicketClick={(ticket) => {
              // Navigate to ticket detail page
              navigate(`/tickets/${ticket.ticket_id}`)
            }}
          />
        </div>
      </main>
    </div>
  )
}
