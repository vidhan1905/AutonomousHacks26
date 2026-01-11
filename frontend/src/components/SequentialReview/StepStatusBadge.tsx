import type { SequentialReviewTicket } from '../../types'

interface StepStatusBadgeProps {
  status: SequentialReviewTicket['status']
}

const statusConfig = {
  step_pending: {
    label: 'Step Pending',
    className: 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200',
  },
  step_accepted: {
    label: 'Step Accepted',
    className: 'bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200',
  },
  step_in_progress: {
    label: 'Step In Progress',
    className: 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200',
  },
  step_completed: {
    label: 'Step Completed',
    className: 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200',
  },
  chain_completed: {
    label: 'Chain Completed',
    className: 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200',
  },
  chain_cancelled: {
    label: 'Chain Cancelled',
    className: 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200',
  },
}

export default function StepStatusBadge({ status }: StepStatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.step_pending

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}
