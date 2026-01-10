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
      <div className="min-h-screen flex items-center justify-center bg-teal-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-500 dark:border-teal-400 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Starting conversation...</p>
        </div>
      </div>
    )
  }

  if (!conversationId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-teal-50 dark:bg-gray-900">
        <div className="text-center text-red-600 dark:text-red-400">
          <p>Failed to start conversation. Please try again.</p>
          <button
            onClick={() => navigate('/dashboard/patient')}
            className="mt-4 px-4 py-2 bg-teal-500 text-white rounded-lg hover:bg-teal-600"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-teal-50 dark:bg-gray-900">
      <ChatInterface conversationId={conversationId} />
    </div>
  )
}
