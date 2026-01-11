import { useEffect, useState, useCallback } from 'react'
import TicketCard from './TicketCard'
import TicketFilters from './TicketFilters'
import type { Ticket } from '../../types'
import { ticketApi } from '../../services/api'

interface TicketDashboardProps {
  userType: 'patient' | 'service_person'
  onTicketClick?: (ticket: Ticket) => void
}

export default function TicketDashboard({ userType: _userType, onTicketClick }: TicketDashboardProps) {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [serviceTypeFilter, setServiceTypeFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')

  const loadTickets = useCallback(async () => {
    setLoading(true)
    try {
      const filters: any = {}
      if (statusFilter !== 'all') filters.status = statusFilter
      if (serviceTypeFilter !== 'all') filters.service_type = serviceTypeFilter
      if (priorityFilter !== 'all') filters.priority = parseInt(priorityFilter)
      
      const data = await ticketApi.list(filters)
      setTickets(data)
    } catch (error) {
      console.error('Failed to load tickets:', error)
      setTickets([])
    } finally {
      setLoading(false)
    }
  }, [statusFilter, serviceTypeFilter, priorityFilter])

  useEffect(() => {
    loadTickets()
  }, [loadTickets])

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-500 dark:border-teal-400"></div>
      </div>
    )
  }

  return (
    <div>
      <TicketFilters
        status={statusFilter}
        serviceType={serviceTypeFilter}
        priority={priorityFilter}
        onStatusChange={setStatusFilter}
        onServiceTypeChange={setServiceTypeFilter}
        onPriorityChange={setPriorityFilter}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tickets.length === 0 ? (
          <div className="col-span-full text-center text-gray-500 dark:text-gray-400 py-12">
            <p>No tickets found</p>
          </div>
        ) : (
          tickets.map((ticket) => (
            <TicketCard 
              key={ticket.ticket_id} 
              ticket={ticket} 
              onClick={onTicketClick}
            />
          ))
        )}
      </div>
    </div>
  )
}
