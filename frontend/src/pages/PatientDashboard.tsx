import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../hooks/useAuth'
import TicketDashboard from '../components/Dashboard/TicketDashboard'
import { conversationApi } from '../services/api'
import type { Conversation } from '../types'

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
      const data = await conversationApi.list(user.id)
      setConversations(data)
    } catch (error) {
      console.error('Failed to load conversations:', error)
    }
  }

  const handleStartChat = async () => {
    try {
      const conversation = await conversationApi.create(user?.id, false)
      navigate(`/chat?conversation_id=${conversation.conversation_id}`)
    } catch (error) {
      console.error('Failed to start conversation:', error)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Patient Dashboard</h1>
              <p className="text-sm text-gray-600">Welcome, {user?.name || 'Patient'}</p>
            </div>
            <div className="flex space-x-4">
              <button
                onClick={handleStartChat}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                Start New Chat
              </button>
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
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">My Tickets</h2>
          <TicketDashboard userType="patient" />
        </div>

        <div className="mt-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Conversations</h2>
          <div className="bg-white rounded-lg shadow-md p-6">
            {conversations.length === 0 ? (
              <p className="text-gray-500">No conversations yet. Start a new chat to begin!</p>
            ) : (
              <div className="space-y-4">
                {conversations.slice(0, 5).map((conv) => (
                  <div
                    key={conv.conversation_id}
                    className="border-b border-gray-200 pb-4 last:border-0 cursor-pointer hover:bg-gray-50 p-2 rounded"
                    onClick={() => navigate(`/chat?conversation_id=${conv.conversation_id}`)}
                  >
                    <p className="text-sm text-gray-600">
                      {new Date(conv.started_at).toLocaleDateString()}
                    </p>
                    <p className="text-sm font-medium text-gray-900">Status: {conv.status}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
