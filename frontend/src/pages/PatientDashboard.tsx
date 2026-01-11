import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../hooks/useAuth'
import { conversationApi } from '../services/api'
import TicketDashboard from '../components/Dashboard/TicketDashboard'
import type { Conversation, Ticket } from '../types'

export default function PatientDashboard() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<Conversation[]>([])

  useEffect(() => {
    if (user?.type !== 'patient') {
      navigate('/login')
      return
    }

    loadConversations()
  }, [user, navigate])

  const loadConversations = async () => {
    if (!user?.id) return
    try {
      // Backend uses authenticated patient automatically
      const data = await conversationApi.list()
      console.log('Loaded conversations:', data)
      setConversations(data)
    } catch (error) {
      console.error('Failed to load conversations:', error)
      setConversations([])
    }
  }

  const handleStartChat = async () => {
    try {
      const conversation = await conversationApi.create()
      navigate(`/chat?conversation_id=${conversation.conversation_id}`)
    } catch (error) {
      console.error('Failed to start conversation:', error)
    }
  }

  const handleTicketClick = (ticket: Ticket) => {
    navigate(`/tickets/${ticket.ticket_id}`)
  }

  return (
    <div className="min-h-screen bg-teal-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Patient Dashboard</h1>
              <p className="text-sm text-gray-600 dark:text-gray-400">Welcome, {user?.name || 'Patient'}</p>
            </div>
            <div className="flex space-x-4">
              <button
                onClick={() => navigate('/profile/edit')}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600"
              >
                Edit Profile
              </button>
              <button
                onClick={handleStartChat}
                className="px-4 py-2 bg-teal-500 text-white rounded-md hover:bg-teal-600"
              >
                Start New Chat
              </button>
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
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          {/* Tickets Section */}
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">My Tickets</h2>
            <TicketDashboard 
              userType="patient" 
              onTicketClick={handleTicketClick}
            />
          </div>

          {/* Conversations Section */}
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Recent Conversations</h2>
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
              {conversations.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-gray-500 dark:text-gray-400 text-lg mb-4">No conversations yet.</p>
                  <p className="text-gray-400 dark:text-gray-500 text-sm">Start a new chat to begin!</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {conversations.map((conv) => (
                    <div
                      key={conv.conversation_id}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 hover:border-teal-300 dark:hover:border-teal-600 transition-colors"
                      onClick={() => navigate(`/chat?conversation_id=${conv.conversation_id}`)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-2">
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                              conv.status === 'active' 
                                ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200' 
                                : conv.status === 'completed'
                                ? 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
                                : 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200'
                            }`}>
                              {conv.status}
                            </span>
                            <span className="text-sm text-gray-500 dark:text-gray-400">
                              {new Date(conv.started_at).toLocaleDateString('en-US', { 
                                year: 'numeric', 
                                month: 'short', 
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit'
                              })}
                            </span>
                          </div>
                          {conv.summary ? (
                            <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2 mt-2">
                              {conv.summary}
                            </p>
                          ) : (
                            <p className="text-sm text-gray-500 dark:text-gray-400 italic mt-2">
                              Click to view conversation
                            </p>
                          )}
                        </div>
                        <svg 
                          className="w-5 h-5 text-gray-400 dark:text-gray-500 ml-4" 
                          fill="none" 
                          stroke="currentColor" 
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
