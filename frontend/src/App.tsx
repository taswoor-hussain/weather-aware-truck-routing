import { useRef, useState } from 'react'
import { requestPlan } from './api'
import { MapPanel } from './components/MapPanel'
import { RouteList } from './components/RouteList'
import { TripForm } from './components/TripForm'
import type { Plan, PlanInput } from './types'

export default function App() {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [selected, setSelected] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const activeRequest = useRef<AbortController | null>(null)

  async function handleSubmit(input: PlanInput) {
    activeRequest.current?.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    setIsLoading(true)
    setError('')
    try {
      const nextPlan = await requestPlan(input, controller.signal)
      setPlan(nextPlan)
      setSelected(nextPlan.routes.find((route) => route.is_recommended)!.name)
    } catch (caught) {
      if (controller.signal.aborted) return
      setError(caught instanceof Error ? caught.message : 'Something went wrong. Please try again.')
    }
    setIsLoading(false)
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <header>
          <h1>Weather-Aware Truck Routing</h1>
          <p>Compare three routes by weather risk at your arrival time, load weight and drive time.</p>
        </header>
        <TripForm isLoading={isLoading} onSubmit={handleSubmit} />
        {error && (
          <p className="notice danger" role="alert">
            {error}
          </p>
        )}
        {plan && <RouteList plan={plan} selected={selected} onSelect={setSelected} />}
      </aside>
      <MapPanel plan={plan} selected={selected} isLoading={isLoading} onSelect={setSelected} />
    </div>
  )
}
