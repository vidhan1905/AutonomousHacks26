import type { DoctorRecommendation } from '../../types'

interface DoctorRecommendationCardProps {
  doctors: DoctorRecommendation[]
  serviceType?: string
}

export default function DoctorRecommendationCard({ doctors, serviceType }: DoctorRecommendationCardProps) {
  const getRankBadgeColor = (rank: number) => {
    switch (rank) {
      case 1:
        return 'bg-yellow-500 text-white'
      case 2:
        return 'bg-gray-400 text-white'
      case 3:
        return 'bg-amber-600 text-white'
      case 4:
        return 'bg-gray-300 text-gray-800'
      case 5:
        return 'bg-gray-200 text-gray-800'
      default:
        return 'bg-gray-200 text-gray-800'
    }
  }

  const getRankLabel = (rank: number) => {
    switch (rank) {
      case 1:
        return 'Best Match'
      case 2:
        return 'Excellent'
      case 3:
        return 'Good'
      case 4:
        return 'Suitable'
      case 5:
        return 'Available'
      default:
        return `Rank #${rank}`
    }
  }

  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-lg p-6 mb-4">
        <h3 className="text-xl font-semibold text-gray-800 mb-2">
          Recommended Doctors
          {serviceType && (
            <span className="ml-2 text-sm font-normal text-gray-600">
              ({serviceType.replace('_', ' ')})
            </span>
          )}
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Based on your medical history and current needs, here are the top {doctors.length} recommended doctors:
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {doctors.map((doctor) => (
          <div
            key={doctor.doctor_id}
            className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow p-5 border-l-4 border-indigo-500"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <h4 className="text-lg font-semibold text-gray-800 mb-1">
                  {doctor.name}
                </h4>
                {doctor.specialization && (
                  <p className="text-sm text-gray-600 mb-2">
                    {doctor.specialization}
                  </p>
                )}
                <p className="text-xs text-gray-500">
                  {doctor.service_type.replace('_', ' ')}
                </p>
              </div>
              <div className="ml-2">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRankBadgeColor(
                    doctor.rank
                  )}`}
                >
                  {getRankLabel(doctor.rank)}
                </span>
              </div>
            </div>

            <div className="mb-3">
              <p className="text-sm text-gray-700 leading-relaxed">
                {doctor.reason}
              </p>
            </div>

            {doctor.ticket_id && (
              <div className="mt-4 pt-3 border-t border-gray-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Ticket ID:</span>
                  <span className="text-xs font-mono text-indigo-600">
                    {doctor.ticket_id.substring(0, 8)}...
                  </span>
                </div>
                <div className="mt-2">
                  <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">
                    Ticket Created
                  </span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 bg-blue-50 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          <strong>Note:</strong> Tickets have been created for all {doctors.length} doctors. 
          You can view and manage them in your dashboard.
        </p>
      </div>
    </div>
  )
}
