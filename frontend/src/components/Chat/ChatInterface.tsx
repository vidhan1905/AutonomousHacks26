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
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <p className="text-lg font-semibold">Welcome to Hospital AI Assistant</p>
            <p className="text-sm mt-2">I'm here to help you. How can I assist you today?</p>
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.message_id} message={message} />
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg p-3 max-w-xs">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
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
