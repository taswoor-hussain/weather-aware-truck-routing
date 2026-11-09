export interface Place {
  label: string
  lat: number
  lon: number
}

export type SampleInterval = 10 | 25 | 50

export interface PlanInput {
  origin: Place
  destination: Place
  departure_at: string
  load_weight_lb: number
  interval_miles: SampleInterval
}

export interface Checkpoint {
  lat: number
  lon: number
  mile: number
  eta: string
  risk: number
  risk_label: string
  reasons: string[]
  wind_mph: number
  rain_in_hr: number
  snow_in_hr: number
}

export interface RouteSummary {
  low_miles: number
  moderate_miles: number
  high_miles: number
  severe_miles: number
  no_travel_miles: number
  average_risk: number
}

export interface RouteOption {
  name: string
  is_recommended: boolean
  distance_miles: number
  duration_seconds: number
  arrival: string
  summary: RouteSummary
  geometry: [number, number][]
  checkpoints: Checkpoint[]
}

export interface HeatmapCell {
  lat: number
  lon: number
  heat: number[]
}

export interface Heatmap {
  start: string
  cell_miles: number
  cells: HeatmapCell[]
}

export interface Plan {
  routes: RouteOption[]
  recommendation: string
  all_routes_blocked: boolean
  heatmap: Heatmap
}
