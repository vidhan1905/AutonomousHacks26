import type { Message } from '../../types'
import DoctorRecommendationCard from '../Doctor/DoctorRecommendationCard'

interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isPatient = message.sender_type === 'patient'
  
  // Check if this is a doctor recommendation message
  const isDoctorRecommendation = 
    message.type === 'doctor_recommendation' ||
    (message.metadata && message.metadata.type === 'doctor_recommendation') ||
    (message.doctors && message.doctors.length > 0)

  if (isDoctorRecommendation && !isPatient && message.doctors) {
    // Render doctor recommendation card
    return (
      <div className="flex justify-start w-full">
        <div className="w-full">
          <DoctorRecommendationCard 
            doctors={message.doctors} 
            serviceType={message.service_type}
          />
          <p className="text-xs text-gray-500 mt-2 ml-2">
            {new Date(message.created_at).toLocaleTimeString()}
          </p>
        </div>
      </div>
    )
  }

  // Regular message bubble
  return (
    <div className={`flex ${isPatient ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
          isPatient
            ? 'bg-indigo-600 text-white'
            : 'bg-gray-100 text-gray-900'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        <p className={`text-xs mt-1 ${isPatient ? 'text-indigo-200' : 'text-gray-500'}`}>
          {new Date(message.created_at).toLocaleTimeString()}
        </p>
      </div>
    </div>
  )
}
