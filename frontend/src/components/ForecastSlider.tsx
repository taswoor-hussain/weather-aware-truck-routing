import { useEffect, useRef, useState } from 'react'
import { formatDateTime } from '../lib/format'
import { RISK_LEVELS } from '../lib/risk'

const MAX_HOUR = 48
const PLAYBACK_HOURS_PER_SECOND = 4

interface Props {
  start: string
  hour: number
  onChange: (hour: number) => void
}

export function ForecastSlider({ start, hour, onChange }: Props) {
  const [isPlaying, setIsPlaying] = useState(false)
  const hourRef = useRef(hour)

  useEffect(() => {
    hourRef.current = hour
  }, [hour])

  useEffect(() => {
    if (!isPlaying) return
    let frame = 0
    let previous = performance.now()
    const tick = (now: number) => {
      const next = hourRef.current + ((now - previous) / 1000) * PLAYBACK_HOURS_PER_SECOND
      previous = now
      if (next >= MAX_HOUR) {
        onChange(MAX_HOUR)
        setIsPlaying(false)
        return
      }
      onChange(next)
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [isPlaying, onChange])

  function togglePlay() {
    if (!isPlaying && hourRef.current >= MAX_HOUR) onChange(0)
    setIsPlaying(!isPlaying)
  }

  const moment = new Date(start).getTime() + Math.round(hour) * 3_600_000
  return (
    <div className="forecast-panel">
      <div className="forecast-heading">
        <button type="button" className="play" onClick={togglePlay} aria-label={isPlaying ? 'Pause forecast' : 'Play forecast'}>
          {isPlaying ? '❚❚' : '▶'}
        </button>
        <div>
          <span className="forecast-title">Corridor forecast</span>
          <output htmlFor="forecast-hour">
            +{Math.round(hour)}h after departure · {formatDateTime(moment)}
          </output>
        </div>
      </div>
      <input
        id="forecast-hour"
        type="range"
        min={0}
        max={MAX_HOUR}
        step={0.25}
        value={hour}
        aria-label="Forecast hours after departure"
        onChange={(event) => {
          setIsPlaying(false)
          onChange(Number(event.target.value))
        }}
      />
      <div className="ticks" aria-hidden="true">
        {[0, 12, 24, 36, 48].map((tick) => (
          <span key={tick}>{tick}h</span>
        ))}
      </div>
      <ul className="legend">
        {RISK_LEVELS.map((level) => (
          <li key={level.label}>
            <i style={{ background: level.color }} />
            {level.label}
          </li>
        ))}
      </ul>
    </div>
  )
}
