import type { FeatureCollection, Point } from 'geojson'
import * as maplibregl from 'maplibre-gl'
import type { ExpressionSpecification, GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useRef, useState } from 'react'
import { formatDateTime, formatDuration, formatMiles } from '../lib/format'
import { HEAT_STOPS, RISK_LEVELS } from '../lib/risk'
import type { Plan, RouteOption } from '../types'

maplibregl.setWorkerUrl(workerUrl)

const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const METERS_PER_MILE = 1609.344
const METERS_PER_PIXEL_AT_ZOOM_0 = 78271.5
const HEAT_RADIUS_FACTOR = 1.35
const LABEL_POSITIONS = [0.5, 0.33, 0.67]
const FIT_PADDING = { top: 70, right: 70, bottom: 190, left: 70 }

const emptyCollection: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** Colour expression for a fractional hour, blending the two adjacent hourly frames. */
function heatColor(hour: number): ExpressionSpecification {
  const lower = Math.floor(hour)
  const upper = Math.min(lower + 1, 48)
  const blend = hour - lower
  const value: ExpressionSpecification = [
    '+',
    ['*', ['get', `h${lower}`], 1 - blend],
    ['*', ['get', `h${upper}`], blend],
  ]
  return ['interpolate', ['linear'], value, ...HEAT_STOPS.flat()] as unknown as ExpressionSpecification
}

function heatRadius(plan: Plan): ExpressionSpecification {
  const meanLat = plan.heatmap.cells.reduce((sum, cell) => sum + cell.lat, 0) / plan.heatmap.cells.length
  const metersPerPixel = METERS_PER_PIXEL_AT_ZOOM_0 * Math.cos((meanLat * Math.PI) / 180)
  const radiusAtZoom0 = (plan.heatmap.cell_miles * METERS_PER_MILE * HEAT_RADIUS_FACTOR) / metersPerPixel
  return ['interpolate', ['exponential', 2], ['zoom'], 0, radiusAtZoom0, 22, radiusAtZoom0 * 2 ** 22]
}

function heatFeatures(plan: Plan): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: plan.heatmap.cells.map((cell) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [cell.lon, cell.lat] },
      properties: Object.fromEntries(cell.heat.map((value, index) => [`h${index}`, value])),
    })),
  }
}

function routeFeatures(plan: Plan): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: plan.routes.map((route) => ({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: route.geometry },
      properties: { name: route.name },
    })),
  }
}

function checkpointFeatures(plan: Plan): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: plan.routes.flatMap((route) =>
      route.checkpoints.map((checkpoint) => ({
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: [checkpoint.lon, checkpoint.lat] },
        properties: {
          route: route.name,
          risk: checkpoint.risk,
          riskLabel: checkpoint.risk_label,
          mile: checkpoint.mile,
          eta: checkpoint.eta,
          wind: checkpoint.wind_mph,
          rain: checkpoint.rain_in_hr,
          snow: checkpoint.snow_in_hr,
          reasons: checkpoint.reasons.join(', '),
        },
      })),
    ),
  }
}

function addLayers(map: MapLibreMap) {
  map.addSource('heat', { type: 'geojson', data: emptyCollection })
  map.addSource('routes', { type: 'geojson', data: emptyCollection })
  map.addSource('checkpoints', { type: 'geojson', data: emptyCollection })

  const firstLabelLayer = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id
  map.addLayer(
    {
      id: 'heat',
      type: 'circle',
      source: 'heat',
      paint: { 'circle-blur': 0.75, 'circle-opacity': 0.62, 'circle-pitch-alignment': 'map' },
    },
    firstLabelLayer,
  )
  map.addLayer({
    id: 'routes-inactive',
    type: 'line',
    source: 'routes',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#51707f', 'line-width': 3.5, 'line-opacity': 0.75 },
  })
  map.addLayer({
    id: 'routes-active-casing',
    type: 'line',
    source: 'routes',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#ffffff', 'line-width': 8 },
  })
  map.addLayer({
    id: 'routes-active',
    type: 'line',
    source: 'routes',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#0b3c49', 'line-width': 5 },
  })
  map.addLayer({
    id: 'checkpoints',
    type: 'circle',
    source: 'checkpoints',
    paint: {
      'circle-color': [
        'match',
        ['get', 'risk'],
        ...RISK_LEVELS.flatMap((level, index) => [index, level.color]),
        '#888888',
      ] as unknown as ExpressionSpecification,
      'circle-stroke-color': '#ffffff',
    },
  })
}

function applySelection(map: MapLibreMap, selected: string) {
  const isSelectedRoute: ExpressionSpecification = ['==', ['get', 'name'], selected]
  map.setFilter('routes-inactive', ['!', isSelectedRoute])
  map.setFilter('routes-active-casing', isSelectedRoute)
  map.setFilter('routes-active', isSelectedRoute)

  const onSelected: ExpressionSpecification = ['==', ['get', 'route'], selected]
  map.setPaintProperty('checkpoints', 'circle-radius', ['case', onSelected, 6, 3.5])
  map.setPaintProperty('checkpoints', 'circle-stroke-width', ['case', onSelected, 1.75, 1])
  map.setPaintProperty('checkpoints', 'circle-opacity', ['case', onSelected, 1, 0.8])
}

function checkpointPopupHtml(properties: Record<string, string | number>): string {
  const level = RISK_LEVELS[Number(properties.risk)]
  const reasons = properties.reasons ? `<p class="popup-reasons">${properties.reasons}</p>` : ''
  return `
    <div class="popup-title"><i style="background:${level.color}"></i>${properties.riskLabel}</div>
    <div class="popup-sub">Route ${properties.route} · Mile ${Math.round(Number(properties.mile))}</div>
    <div class="popup-eta">ETA ${formatDateTime(String(properties.eta))}</div>
    <dl>
      <dt>Wind</dt><dd>${properties.wind} mph</dd>
      <dt>Rain</dt><dd>${properties.rain} in/hr</dd>
      <dt>Snow</dt><dd>${properties.snow} in/hr</dd>
    </dl>
    ${reasons}`
}

function routeLabel(route: RouteOption, onSelect: (name: string) => void): HTMLButtonElement {
  const { summary } = route
  const worstRisk = RISK_LEVELS.findLastIndex((level) => summary[level.key] > 0)
  const element = document.createElement('button')
  element.type = 'button'
  element.className = 'route-label'
  element.setAttribute('aria-label', `Select route ${route.name}`)

  const title = document.createElement('span')
  title.className = 'route-label-title'
  const dot = document.createElement('i')
  dot.style.background = RISK_LEVELS[Math.max(worstRisk, 0)].color
  title.append(dot, `${route.name}${route.is_recommended ? ' ★' : ''} · ${formatDuration(route.duration_seconds)}`)

  const detail = document.createElement('span')
  const severe = summary.severe_miles + summary.no_travel_miles
  detail.textContent = `${formatMiles(route.distance_miles)} · Severe ${Math.round(severe)} · High ${Math.round(summary.high_miles)} · Avg ${summary.average_risk.toFixed(2)}`

  element.append(title, detail)
  element.addEventListener('click', () => onSelect(route.name))
  return element
}

function endpointMarker(text: string, coordinates: [number, number], map: MapLibreMap) {
  const element = document.createElement('div')
  element.className = 'endpoint'
  element.textContent = text
  return new maplibregl.Marker({ element }).setLngLat(coordinates).addTo(map)
}

interface Props {
  plan: Plan | null
  selected: string
  hour: number
  onSelect: (name: string) => void
}

export function RouteMap({ plan, selected, hour, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const labelsRef = useRef(new Map<string, HTMLElement>())
  const onSelectRef = useRef(onSelect)
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current!,
      style: STYLE_URL,
      center: [-96, 38],
      zoom: 3.6,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('load', () => {
      addLayers(map)
      mapRef.current = map
      setIsReady(true)
    })

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, maxWidth: '240px' })
    const showPopup = (event: maplibregl.MapLayerMouseEvent) => {
      const feature = event.features?.[0]
      if (!feature) return
      popup
        .setLngLat((feature.geometry as Point).coordinates as [number, number])
        .setHTML(checkpointPopupHtml(feature.properties))
        .addTo(map)
    }
    map.on('mousemove', 'checkpoints', (event) => {
      map.getCanvas().style.cursor = 'pointer'
      showPopup(event)
    })
    map.on('mouseleave', 'checkpoints', () => {
      map.getCanvas().style.cursor = ''
      popup.remove()
    })
    map.on('click', 'checkpoints', showPopup)
    map.on('click', 'routes-inactive', (event) => {
      const name = event.features?.[0]?.properties.name
      if (name) onSelectRef.current(name)
    })

    return () => {
      mapRef.current = null
      setIsReady(false)
      map.remove()
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!isReady || !map || !plan) return

    ;(map.getSource('heat') as GeoJSONSource).setData(heatFeatures(plan))
    ;(map.getSource('routes') as GeoJSONSource).setData(routeFeatures(plan))
    ;(map.getSource('checkpoints') as GeoJSONSource).setData(checkpointFeatures(plan))
    map.setPaintProperty('heat', 'circle-radius', heatRadius(plan))

    const labels = new Map<string, HTMLElement>()
    const markers = plan.routes.map((route, index) => {
      const element = routeLabel(route, (name) => onSelectRef.current(name))
      labels.set(route.name, element)
      const position = route.geometry[Math.floor(route.geometry.length * LABEL_POSITIONS[index])]
      return new maplibregl.Marker({ element }).setLngLat(position).addTo(map)
    })
    labelsRef.current = labels

    const line = plan.routes[0].geometry
    markers.push(endpointMarker('Start', line[0], map), endpointMarker('End', line[line.length - 1], map))

    const bounds = new maplibregl.LngLatBounds()
    plan.routes.forEach((route) => route.geometry.forEach((point) => bounds.extend(point)))
    map.fitBounds(bounds, { padding: FIT_PADDING, duration: 700 })

    return () => markers.forEach((marker) => marker.remove())
  }, [plan, isReady])

  useEffect(() => {
    const map = mapRef.current
    if (!isReady || !map || !plan) return
    applySelection(map, selected)
    labelsRef.current.forEach((element, name) => element.classList.toggle('selected', name === selected))
  }, [plan, selected, isReady])

  useEffect(() => {
    const map = mapRef.current
    if (!isReady || !map || !plan) return
    map.setPaintProperty('heat', 'circle-color', heatColor(hour))
  }, [plan, hour, isReady])

  return <div ref={containerRef} className="map" />
}
