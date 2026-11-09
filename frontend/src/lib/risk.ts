export const RISK_LEVELS = [
  { label: 'Low', color: '#2f9e6e', key: 'low_miles' },
  { label: 'Moderate', color: '#e3b505', key: 'moderate_miles' },
  { label: 'High', color: '#ee7f1f', key: 'high_miles' },
  { label: 'Severe', color: '#d62839', key: 'severe_miles' },
  { label: 'No Travel', color: '#6a1b8a', key: 'no_travel_miles' },
] as const

/**
 * Heatmap colour stops on the backend's 0-40 scale. Each level gets its own
 * pale-to-saturated ramp, and the colour changes hue only at a level boundary,
 * so a colour on the map always matches the checkpoint risk level.
 */
export const HEAT_STOPS: [number, string][] = [
  [0, '#cfeadb'],
  [9.9, '#2f9e6e'],
  [10, '#f6e6a0'],
  [19.9, '#e3b505'],
  [20, '#f8c896'],
  [29.9, '#ee7f1f'],
  [30, '#ef8f98'],
  [39.9, '#d62839'],
  [40, '#6a1b8a'],
]
