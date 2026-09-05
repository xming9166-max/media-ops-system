import AppProviders from './providers/AppProviders'
import AppRouter from './router/AppRouter'
import ErrorBoundary from '@/components/common/ErrorBoundary'

function App() {
  return (
    <ErrorBoundary>
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </ErrorBoundary>
  )
}

export default App
