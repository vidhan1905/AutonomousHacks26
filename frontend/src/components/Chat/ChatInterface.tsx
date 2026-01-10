import { useEffect, useRef, useState } from 'react'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import type { Message } from '../../types'
import { conversationApi } from '../../services/api'

interface ChatInterfaceProps {
  conversationId: string
}

export default function ChatInterface({ conversationId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadMessages()
  }, [conversationId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const loadMessages = async () => {
    try {
      const msgs = await conversationApi.getMessages(conversationId)
      setMessages(msgs)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return

    // Add user message optimistically for immediate UI feedback
    const userMessage: Message = {
      message_id: `temp-${Date.now()}`,
      sender_type: 'patient',
      content,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setLoading(true)

    try {
      // Send message - this will process it through the workflow
      await conversationApi.sendMessage(conversationId, content)
      
      // After sending, reload all messages from the checkpointer to get the complete, correct list
      // This ensures we have all messages in the correct order without duplicates
      await loadMessages()
    } catch (error) {
      console.error('Failed to send message:', error)
      // Remove optimistic user message on error
      setMessages((prev) => prev.filter(msg => msg.message_id !== userMessage.message_id))
      const errorMessage: Message = {
        message_id: `error-${Date.now()}`,
        sender_type: 'llm',
        content: 'Sorry, I encountered an error. Please try again.',
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full w-full">
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">AI Assistant Chat</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">Chatting with Hospital AI Assistant</p>
        </div>
        <button
          onClick={() => window.history.back()}
          className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-teal-50 dark:hover:bg-teal-900/20"
        >
          Back
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-teal-50 dark:bg-gray-900">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 dark:text-gray-400 mt-8">
            <p className="text-lg font-semibold">Welcome to Hospital AI Assistant</p>
            <p className="text-sm mt-2">I'm here to help you. How can I assist you today?</p>
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.message_id} message={message} />
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3 max-w-xs">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <ChatInput onSend={handleSendMessage} disabled={loading} />
    </div>
  )
}
