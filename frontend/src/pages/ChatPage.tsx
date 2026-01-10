import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ChatInterface from '../components/Chat/ChatInterface'
import { useAuthStore } from '../hooks/useAuth'
import { conversationApi } from '../services/api'

export default function ChatPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) {
      navigate('/login')
      return
    }

    const initializeConversation = async () => {
      try {
        // Check if conversation_id is provided in URL query params
        const existingConversationId = searchParams.get('conversation_id')
        
        if (existingConversationId) {
          // Use existing conversation
          console.log('Loading existing conversation:', existingConversationId)
          // Verify conversation exists by fetching it
          try {
            await conversationApi.get(existingConversationId)
            setConversationId(existingConversationId)
          } catch (error) {
            console.error('Failed to load conversation:', error)
            // If conversation doesn't exist, create a new one
            const patientId = user.type === 'patient' ? user.id : undefined
            const conversation = await conversationApi.create(patientId, user.type !== 'patient')
            setConversationId(conversation.conversation_id)
            // Update URL to reflect new conversation
            navigate(`/chat?conversation_id=${conversation.conversation_id}`, { replace: true })
          }
        } else {
          // Create new conversation
          console.log('Creating new conversation')
          const patientId = user.type === 'patient' ? user.id : undefined
          const conversation = await conversationApi.create(patientId, user.type !== 'patient')
          setConversationId(conversation.conversation_id)
          // Update URL to include new conversation ID
          navigate(`/chat?conversation_id=${conversation.conversation_id}`, { replace: true })
        }
      } catch (error) {
        console.error('Failed to initialize conversation:', error)
      } finally {
        setLoading(false)
      }
    }

    initializeConversation()
  }, [user, navigate, searchParams])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Starting conversation...</p>
        </div>
      </div>
    )
  }

  if (!conversationId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center text-red-600">
          <p>Failed to start conversation. Please try again.</p>
          <button
            onClick={() => navigate('/dashboard/patient')}
            className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">AI Assistant Chat</h1>
              <p className="text-sm text-gray-600">Chatting with Hospital AI Assistant</p>
            </div>
            <button
              onClick={() => navigate('/dashboard/patient')}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-4xl mx-auto w-full mt-8 mb-8">
        <div className="bg-white rounded-lg shadow-lg h-[600px] flex flex-col">
          <ChatInterface conversationId={conversationId} />
        </div>
      </main>
    </div>
  )
}
