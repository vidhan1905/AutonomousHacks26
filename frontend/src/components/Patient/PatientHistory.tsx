interface PatientHistoryProps {
  history: any[]
}

export default function PatientHistory({ history }: PatientHistoryProps) {
  if (!history || history.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-md p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Medical History</h3>
        <p className="text-gray-500 text-sm">No history available</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Medical History</h3>
      <div className="space-y-4">
        {history.map((record, index) => (
          <div key={index} className="border-b border-gray-200 pb-4 last:border-0">
            <div className="flex justify-between items-start mb-2">
              <span className="text-sm font-medium text-gray-900">
                {new Date(record.visit_date).toLocaleDateString()}
              </span>
              <span className="text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">
                {record.service_type}
              </span>
            </div>
            {record.diagnosis && (
              <p className="text-sm text-gray-700">
                <span className="font-medium">Diagnosis:</span> {record.diagnosis}
              </p>
            )}
            {record.treatment && (
              <p className="text-sm text-gray-700 mt-1">
                <span className="font-medium">Treatment:</span> {record.treatment}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
