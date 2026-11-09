import { useState } from 'react'
import type { Plan } from '../types'
import { ForecastSlider } from './ForecastSlider'
import { RouteMap } from './RouteMap'

interface Props {
  plan: Plan | null
  selected: string
  isLoading: boolean
  onSelect: (name: string) => void
}

/** Owns the slider state so dragging re-renders only the map, never the sidebar. */
export function MapPanel({ plan, selected, isLoading, onSelect }: Props) {
  const [hour, setHour] = useState(0)
  const [planForHour, setPlanForHour] = useState(plan)
  if (plan !== planForHour) {
    setPlanForHour(plan)
    setHour(0)
  }

  return (
    <main className="map-panel">
      <RouteMap plan={plan} selected={selected} hour={hour} onSelect={onSelect} />
      {plan && <ForecastSlider start={plan.heatmap.start} hour={hour} onChange={setHour} />}
      {isLoading && (
        <div className="loading" role="status">
          <span className="spinner" />
          Finding truck routes and checking the forecast at each checkpoint…
        </div>
      )}
    </main>
  )
}
