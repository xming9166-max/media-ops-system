import AppProviders from './providers/AppProviders'
import AppRouter from './router/AppRouter'

function App() {
  return (
    <AppProviders>
      <AppRouter />
    </AppProviders>
  )
}

export default App
