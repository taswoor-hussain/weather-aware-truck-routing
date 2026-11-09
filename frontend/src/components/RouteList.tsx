import { formatDateTime, formatDuration, formatMiles } from '../lib/format'
import { RISK_LEVELS } from '../lib/risk'
import type { Plan, RouteOption } from '../types'

interface Props {
  plan: Plan
  selected: string
  onSelect: (name: string) => void
}

export function RouteList({ plan, selected, onSelect }: Props) {
  const recommended = plan.routes.find((route) => route.is_recommended)!
  return (
    <section className="results" aria-label="Route options">
      {plan.all_routes_blocked ? (
        <p className="notice danger" role="alert">
          <strong>Do not depart at this time.</strong> Every route crosses No Travel conditions.
          Route {recommended.name} is the least bad option.
        </p>
      ) : (
        <p className="notice">
          <strong>Take Route {recommended.name}.</strong> {plan.recommendation}
        </p>
      )}
      {plan.routes.map((route) => (
        <RouteCard
          key={route.name}
          route={route}
          isSelected={route.name === selected}
          onSelect={() => onSelect(route.name)}
        />
      ))}
    </section>
  )
}

function RouteCard({
  route,
  isSelected,
  onSelect,
}: {
  route: RouteOption
  isSelected: boolean
  onSelect: () => void
}) {
  const { summary } = route
  return (
    <button className={`route-card${isSelected ? ' selected' : ''}`} aria-pressed={isSelected} onClick={onSelect}>
      <span className="route-heading">
        <strong>Route {route.name}</strong>
        {route.is_recommended && <span className="badge">Recommended</span>}
        <span className="route-duration">{formatDuration(route.duration_seconds)}</span>
      </span>
      <span className="route-meta">
        {formatMiles(route.distance_miles)} · Arrives {formatDateTime(route.arrival)}
      </span>
      <span className="risk-bar" aria-hidden="true">
        {RISK_LEVELS.map((level) => (
          <span key={level.key} style={{ flexGrow: summary[level.key], background: level.color }} />
        ))}
      </span>
      <span className="route-stats">
        <Stat label="Severe" value={formatMiles(summary.severe_miles + summary.no_travel_miles)} />
        <Stat label="High" value={formatMiles(summary.high_miles)} />
        <Stat label="Avg risk" value={`${summary.average_risk.toFixed(2)} / 4`} />
      </span>
      {summary.no_travel_miles > 0 && (
        <span className="no-travel">Includes {formatMiles(summary.no_travel_miles)} of No Travel</span>
      )}
    </button>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="stat">
      <span>{label}</span>
      <b>{value}</b>
    </span>
  )
}
