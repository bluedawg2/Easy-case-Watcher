import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReviewQueue } from './ReviewQueue'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ReviewQueue />
    </QueryClientProvider>
  )
}
