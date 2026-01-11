import { useEffect, useState, useCallback } from 'react'
import TicketCard from './TicketCard'
import TicketFilters from './TicketFilters'
import type { Ticket, SequentialReviewTicket } from '../../types'
import { ticketApi, sequentialReviewTicketApi } from '../../services/api'

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

interface TicketDashboardProps {
  userType: 'patient' | 'service_person'
  onTicketClick?: (ticket: Ticket) => void
}

export default function TicketDashboard({ userType: _userType, onTicketClick }: TicketDashboardProps) {
  // #region agent log
  logDebug('TicketDashboard.tsx:12', 'Component rendering', { userType: _userType }, 'A')
  // #endregion
  
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [serviceTypeFilter, setServiceTypeFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  
  // #region agent log
  logDebug('TicketDashboard.tsx:18', 'State initialized', { loading, ticketsCount: tickets.length }, 'A')
  // #endregion

  const loadTickets = useCallback(async () => {
    console.log('TicketDashboard: loadTickets called')
    setLoading(true)
    try {
      const filters: any = {}
      if (statusFilter !== 'all') filters.status = statusFilter
      if (serviceTypeFilter !== 'all') filters.service_type = serviceTypeFilter
      if (priorityFilter !== 'all') filters.priority = parseInt(priorityFilter)
      
      // Load both regular tickets and sequential review tickets
      let regularTickets: Ticket[] = []
      let sequentialTickets: SequentialReviewTicket[] = []
      
      try {
        regularTickets = await ticketApi.list(filters)
        console.log('Loaded regular tickets:', regularTickets.length)
      } catch (err: any) {
        console.error('Failed to load regular tickets:', err)
        console.error('Error details:', err.response?.data || err.message)
      }
      
      try {
        sequentialTickets = await sequentialReviewTicketApi.list(statusFilter !== 'all' ? { status: statusFilter } : {})
        console.log('Loaded sequential review tickets:', sequentialTickets.length)
      } catch (err: any) {
        console.error('Failed to load sequential review tickets:', err)
        console.error('Error details:', err.response?.data || err.message)
        // If table doesn't exist yet, that's okay - just return empty array
        if (err.response?.status === 500 && err.response?.data?.detail?.includes('does not exist')) {
          console.log('Sequential review tickets table may not exist yet, skipping...')
        }
      }
      
      // Combine tickets (mark sequential review tickets for routing)
      // Convert SequentialReviewTicket to Ticket-like format for display
      const sequentialAsTickets = sequentialTickets.map((t: SequentialReviewTicket) => ({
        ticket_id: t.ticket_id,
        conversation_id: t.conversation_id,
        patient_id: t.patient_id,
        service_type: t.current_step?.service_type || 'sequential_review',
        status: t.status,
        priority: 3, // Default priority for sequential reviews
        assigned_to: t.current_step?.doctor_id || null,
        description: t.description,
        patient_details: t.patient_details,
        past_history_summary: t.past_history_summary,
        llm_summary: t.llm_summary,
        current_symptoms: null,
        created_at: t.created_at,
        assigned_at: null,
        completed_at: t.chain_completed_at,
        is_sequential_review: true,
        sequential_review_chain_id: t.chain_id,
        ticket_type: 'sequential_review' as const,
        step_index: t.step_index, // Add step_index
        can_start: t.can_start, // Add can_start
      }))
      
      const allTickets = [
        ...regularTickets,
        ...sequentialAsTickets,
      ] as (Ticket & { ticket_type?: 'sequential_review' })[]
      
      // #region agent log
      logDebug('TicketDashboard.tsx:80', 'Before setTickets', { totalCount: allTickets.length, regularCount: regularTickets.length, sequentialCount: sequentialTickets.length }, 'E')
      // #endregion
      console.log('Total tickets to display:', allTickets.length)
      setTickets(allTickets as Ticket[])
      // #region agent log
      logDebug('TicketDashboard.tsx:83', 'setTickets called', { count: allTickets.length }, 'E')
      // #endregion
    } catch (error: any) {
      // #region agent log
      logDebug('TicketDashboard.tsx:86', 'loadTickets catch block', { 
        error: error?.message, 
        stack: error?.stack?.substring(0, 200) 
      }, 'E')
      // #endregion
      console.error('Failed to load tickets:', error)
      setTickets([])
    } finally {
      // #region agent log
      logDebug('TicketDashboard.tsx:92', 'loadTickets finally - setLoading(false)', {}, 'E')
      // #endregion
      setLoading(false)
    }
  }, [statusFilter, serviceTypeFilter, priorityFilter])

  useEffect(() => {
    // #region agent log
    logDebug('TicketDashboard.tsx:90', 'useEffect for loadTickets triggered', { loadTicketsExists: !!loadTickets }, 'A')
    // #endregion
    console.log('TicketDashboard: useEffect triggered, loading tickets...')
    loadTickets()
  }, [loadTickets])
  
  useEffect(() => {
    // #region agent log
    logDebug('TicketDashboard.tsx:97', 'Component state updated', { 
      ticketsCount: tickets.length, 
      loading,
      statusFilter,
      serviceTypeFilter,
      priorityFilter
    }, 'A')
    // #endregion
    console.log('TicketDashboard: Component mounted/updated', { 
      ticketsCount: tickets.length, 
      loading,
      statusFilter,
      serviceTypeFilter,
      priorityFilter
    })
  }, [tickets.length, loading, statusFilter, serviceTypeFilter, priorityFilter])

  // #region agent log
  logDebug('TicketDashboard.tsx:105', 'Render decision', { loading, ticketsCount: tickets.length }, 'A')
  // #endregion
  
  if (loading) {
    // #region agent log
    logDebug('TicketDashboard.tsx:108', 'Rendering loading state', {}, 'A')
    // #endregion
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-500 dark:border-teal-400"></div>
      </div>
    )
  }

  // #region agent log
  logDebug('TicketDashboard.tsx:117', 'Rendering ticket list', { ticketsCount: tickets.length }, 'A')
  // #endregion
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
