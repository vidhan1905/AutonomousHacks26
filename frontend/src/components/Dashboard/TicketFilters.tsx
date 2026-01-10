interface TicketFiltersProps {
  status: string
  serviceType: string
  priority: string
  onStatusChange: (status: string) => void
  onServiceTypeChange: (type: string) => void
  onPriorityChange: (priority: string) => void
}

const SERVICE_TYPES = [
  'all',
  'general_consultation',
  'emergency',
  'cardiology',
  'neurology',
  'orthopedics',
  'pediatrics',
  'gynecology',
  'dermatology',
  'mental_health',
  'physical_therapy',
  'surgery_consultation',
  'blood_test',
  'lab_test',
  'imaging',
  'pain_management',
]

export default function TicketFilters({
  status,
  serviceType,
  priority,
  onStatusChange,
  onServiceTypeChange,
  onPriorityChange,
}: TicketFiltersProps) {
  return (
    <div className="bg-white rounded-lg shadow-md p-4 mb-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Status
          </label>
          <select
            value={status}
            onChange={(e) => onStatusChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="assigned">Assigned</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Service Type
          </label>
          <select
            value={serviceType}
            onChange={(e) => onServiceTypeChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
          >
            {SERVICE_TYPES.map((type) => (
              <option key={type} value={type}>
                {type.replace('_', ' ').toUpperCase()}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Priority
          </label>
          <select
            value={priority}
            onChange={(e) => onPriorityChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
          >
            <option value="all">All</option>
            <option value="1">1 - Lowest</option>
            <option value="2">2 - Low</option>
            <option value="3">3 - Medium</option>
            <option value="4">4 - High</option>
            <option value="5">5 - Highest</option>
          </select>
        </div>
      </div>
    </div>
  )
}
