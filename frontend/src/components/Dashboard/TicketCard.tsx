import { useNavigate } from 'react-router-dom'
import type { Ticket } from '../../types'

interface TicketCardProps {
  ticket: Ticket
  onClick?: (ticket: Ticket) => void
}

const priorityColors = {
  1: 'bg-green-100 text-green-800',
  2: 'bg-blue-100 text-blue-800',
  3: 'bg-yellow-100 text-yellow-800',
  4: 'bg-orange-100 text-orange-800',
  5: 'bg-red-100 text-red-800',
}

const statusColors = {
  open: 'bg-gray-100 text-gray-800',
  assigned: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
}

export default function TicketCard({ ticket, onClick }: TicketCardProps) {
  const navigate = useNavigate()

  const handleClick = () => {
    if (onClick) {
      onClick(ticket)
    } else {
      // Navigate to ticket detail page
      navigate(`/tickets/${ticket.ticket_id}`)
    }
  }

  return (
    <div
      className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer"
      onClick={handleClick}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {ticket.service_type.replace('_', ' ').toUpperCase()}
          </h3>
          <p className="text-sm text-gray-600 mt-1">
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
      <p className="text-gray-700 text-sm line-clamp-2">{ticket.description}</p>
      {ticket.assigned_to && (
        <p className="text-xs text-gray-500 mt-2">Assigned</p>
      )}
    </div>
  )
}
