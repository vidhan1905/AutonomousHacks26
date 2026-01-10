import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../hooks/useAuth'
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
      console.log('Loading conversations for patient:', user.id)
      const data = await conversationApi.list(user.id)
      console.log('Loaded conversations:', data)
      setConversations(data)
    } catch (error) {
      console.error('Failed to load conversations:', error)
      setConversations([])
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
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Conversations</h2>
          <div className="bg-white rounded-lg shadow-md p-6">
            {conversations.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500 text-lg mb-4">No conversations yet.</p>
                <p className="text-gray-400 text-sm">Start a new chat to begin!</p>
              </div>
            ) : (
              <div className="space-y-3">
                {conversations.map((conv) => (
                  <div
                    key={conv.conversation_id}
                    className="border border-gray-200 rounded-lg p-4 cursor-pointer hover:bg-gray-50 hover:border-indigo-300 transition-colors"
                    onClick={() => navigate(`/chat?conversation_id=${conv.conversation_id}`)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                            conv.status === 'active' 
                              ? 'bg-green-100 text-green-800' 
                              : conv.status === 'completed'
                              ? 'bg-gray-100 text-gray-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {conv.status}
                          </span>
                          <span className="text-sm text-gray-500">
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
                          <p className="text-sm text-gray-700 line-clamp-2 mt-2">
                            {conv.summary}
                          </p>
                        ) : (
                          <p className="text-sm text-gray-500 italic mt-2">
                            Click to view conversation
                          </p>
                        )}
                      </div>
                      <svg 
                        className="w-5 h-5 text-gray-400 ml-4" 
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
      </main>
    </div>
  )
}
