import { useNavigate } from 'react-router-dom'
import type { Ticket } from '../../types'

interface TicketCardProps {
  ticket: Ticket
  onClick?: (ticket: Ticket) => void
}

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

export default function TicketCard({ ticket, onClick }: TicketCardProps) {
  const navigate = useNavigate()

  const handleClick = () => {
    if (onClick) {
      onClick(ticket)
    } else {
      navigate(`/tickets/${ticket.ticket_id}`)
    }
  }

  return (
    <div
      className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer"
      onClick={handleClick}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {ticket.service_type.replace('_', ' ').toUpperCase()}
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {new Date(ticket.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex space-x-2">
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${priorityColors[ticket.priority as keyof typeof priorityColors]}`}>
            Priority {ticket.priority}
          </span>
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[ticket.status as keyof typeof statusColors]}`}>
            {ticket.status}
          </span>
        </div>
      </div>
      <p className="text-gray-700 dark:text-gray-300 text-sm line-clamp-2">{ticket.description}</p>
      {ticket.assigned_to && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">Assigned</p>
      )}
    </div>
  )
}
