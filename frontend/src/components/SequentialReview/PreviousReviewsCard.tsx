interface PreviousReviewsCardProps {
  previousReviews: string | null
}

export default function PreviousReviewsCard({ previousReviews }: PreviousReviewsCardProps) {
  if (!previousReviews || previousReviews === 'No previous reviews.') {
    return null
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Previous Doctors' Reviews
      </h3>
      <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
        <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap text-sm">
          {previousReviews}
        </p>
      </div>
    </div>
  )
}
