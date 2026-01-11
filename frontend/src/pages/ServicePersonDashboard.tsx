import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../hooks/useAuth'
import TicketDashboard from '../components/Dashboard/TicketDashboard'
import type { Ticket } from '../types'

// #region agent log
const DEBUG_LOG_PATH = '/Users/vidhan/Vidhan/GDG FINAL/AutonomousHacks26/.cursor/debug.log'
const logDebug = (location: string, message: string, data: any = {}, hypothesisId?: string) => {
  const payload = {
    sessionId: 'debug-session',
    runId: 'run1',
    hypothesisId: hypothesisId || 'A',
    location,
    message,
    data,
    timestamp: Date.now()
  }
  fetch('http://127.0.0.1:7242/ingest/a61d17be-af11-4c91-8ff2-4d1814fc0e77', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(() => {})
}
// #endregion

export default function ServicePersonDashboard() {
  // #region agent log
  logDebug('ServicePersonDashboard.tsx:6', 'ServicePersonDashboard rendering', {}, 'A')
  // #endregion
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  
  // #region agent log
  logDebug('ServicePersonDashboard.tsx:10', 'User state', { 
    userExists: !!user, 
    userType: user?.type,
    userId: user?.id 
  }, 'A')
  // #endregion

  const handleTicketClick = (ticket: Ticket & { ticket_type?: 'sequential_review' }) => {
    // Navigate to appropriate ticket detail page
    if (ticket.ticket_type === 'sequential_review' || ticket.is_sequential_review) {
      navigate(`/tickets/sequential-review/${ticket.ticket_id}`)
    } else {
      navigate(`/tickets/${ticket.ticket_id}`)
    }
  }

  return (
    <div className="min-h-screen bg-teal-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Service Person Dashboard</h1>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Welcome, {user?.name || user?.username} - {user?.service_type?.replace('_', ' ')}
              </p>
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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Your Tickets</h2>
          {/* #region agent log */}
          {(() => {
            logDebug('ServicePersonDashboard.tsx:46', 'Rendering TicketDashboard component', {}, 'A')
            return null
          })()}
          {/* #endregion */}
          <TicketDashboard 
            userType="service_person" 
            onTicketClick={handleTicketClick}
          />
        </div>
      </main>
    </div>
  )
}
