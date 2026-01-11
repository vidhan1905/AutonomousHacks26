import type { SequentialReviewTicket } from '../../types'

interface StepProgressIndicatorProps {
  ticket: SequentialReviewTicket
  progress: {
    total_steps: number
    current_step: number
    completed_steps: number
    steps: Array<{
      step_number: number
      doctor_name: string
      service_type: string
      status: string
      completed_at: string | null
      review_summary: string | null
      review_notes: string | null
    }>
  }
}

export default function StepProgressIndicator({ ticket, progress }: StepProgressIndicatorProps) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
        Sequential Review Progress
      </h2>
      
      <div className="space-y-3">
        {progress.steps.map((step, idx) => (
          <div
            key={idx}
            className={`flex items-start space-x-3 p-3 rounded-lg border ${
              step.status === 'completed'
                ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/30'
                : step.status === 'in_review'
                ? 'border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/30'
                : step.step_number === progress.current_step
                ? 'border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/30'
                : 'border-gray-200 dark:border-gray-700'
            }`}
          >
            <div
              className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                step.status === 'completed'
                  ? 'bg-green-500 text-white'
                  : step.status === 'in_review'
                  ? 'bg-yellow-500 text-white'
                  : step.step_number === progress.current_step
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
              }`}
            >
              {step.status === 'completed' ? '✓' : step.step_number}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">
                    Step {step.step_number} of {progress.total_steps}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {step.doctor_name} ({step.service_type})
                  </p>
                </div>
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    step.status === 'completed'
                      ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
                      : step.status === 'in_review'
                      ? 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
                  }`}
                >
                  {step.status === 'completed'
                    ? 'Completed'
                    : step.status === 'in_review'
                    ? 'In Progress'
                    : 'Pending'}
                </span>
              </div>
              {step.status === 'completed' && step.completed_at && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Completed: {new Date(step.completed_at).toLocaleString()}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Progress: {progress.completed_steps} of {progress.total_steps} steps completed
        </p>
      </div>
    </div>
  )
}
