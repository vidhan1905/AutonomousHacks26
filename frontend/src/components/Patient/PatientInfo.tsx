interface PatientInfoProps {
  name?: string
  phone?: string
  dateOfBirth?: string
  bloodGroup?: string
  verified: boolean
}

export default function PatientInfo({
  name,
  phone,
  dateOfBirth,
  bloodGroup,
  verified,
}: PatientInfoProps) {
  if (!verified) return null

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Patient Information</h3>
      <div className="space-y-2 text-sm">
        {name && (
          <div>
            <span className="font-medium text-gray-700">Name:</span>
            <span className="ml-2 text-gray-900">{name}</span>
          </div>
        )}
        {phone && (
          <div>
            <span className="font-medium text-gray-700">Phone:</span>
            <span className="ml-2 text-gray-900">{phone}</span>
          </div>
        )}
        {dateOfBirth && (
          <div>
            <span className="font-medium text-gray-700">Date of Birth:</span>
            <span className="ml-2 text-gray-900">{dateOfBirth}</span>
          </div>
        )}
        {bloodGroup && (
          <div>
            <span className="font-medium text-gray-700">Blood Group:</span>
            <span className="ml-2 text-gray-900">{bloodGroup}</span>
          </div>
        )}
        <div className="mt-2">
          <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
            Verified
          </span>
        </div>
      </div>
    </div>
  )
}
