import { useState } from 'react'
import { toLocalInputValue } from '../lib/format'
import type { Place, PlanInput, SampleInterval } from '../types'
import { PlaceInput } from './PlaceInput'

const INTERVALS: SampleInterval[] = [10, 25, 50]
const MAX_LOAD_LB = 80_000

function defaultDeparture(): string {
  const date = new Date(Date.now() + 60 * 60 * 1000)
  date.setMinutes(0, 0, 0)
  return toLocalInputValue(date)
}

interface Props {
  isLoading: boolean
  onSubmit: (input: PlanInput) => void
}

interface FieldErrors {
  origin?: string
  destination?: string
  load?: string
}

export function TripForm({ isLoading, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState(defaultDeparture)
  const [load, setLoad] = useState('35000')
  const [interval, setInterval] = useState<SampleInterval>(25)
  const [errors, setErrors] = useState<FieldErrors>({})

  function submit(sampleInterval: SampleInterval) {
    const loadLb = Number(load)
    const nextErrors: FieldErrors = {}
    if (!origin) nextErrors.origin = 'Choose a place from the suggestions.'
    if (!destination) nextErrors.destination = 'Choose a place from the suggestions.'
    if (!Number.isInteger(loadLb) || loadLb < 1 || loadLb > MAX_LOAD_LB) {
      nextErrors.load = `Enter a whole number from 1 to ${MAX_LOAD_LB.toLocaleString()}.`
    }
    setErrors(nextErrors)
    if (!origin || !destination || Object.keys(nextErrors).length > 0) return

    onSubmit({
      origin,
      destination,
      departure_at: new Date(departure).toISOString(),
      load_weight_lb: loadLb,
      interval_miles: sampleInterval,
    })
  }

  function changeInterval(next: SampleInterval) {
    setInterval(next)
    // Resample straight away once a trip is filled in.
    if (origin && destination) submit(next)
  }

  return (
    <form
      className="trip-form"
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        submit(interval)
      }}
    >
      <PlaceInput label="Origin" placeholder="City or address" error={errors.origin} onChange={setOrigin} />
      <PlaceInput
        label="Destination"
        placeholder="City or address"
        error={errors.destination}
        onChange={setDestination}
      />
      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            required
            value={departure}
            onChange={(event) => setDeparture(event.target.value)}
          />
        </div>
        <div className="field load-field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            min={1}
            max={MAX_LOAD_LB}
            step={500}
            aria-invalid={Boolean(errors.load)}
            value={load}
            onChange={(event) => setLoad(event.target.value)}
          />
        </div>
      </div>
      {errors.load && <p className="field-error">{errors.load}</p>}
      <fieldset className="field segmented">
        <legend>Check weather every</legend>
        <div>
          {INTERVALS.map((option) => (
            <label key={option} className={option === interval ? 'selected' : undefined}>
              <input
                type="radio"
                name="interval"
                checked={option === interval}
                onChange={() => changeInterval(option)}
              />
              {option} mi
            </label>
          ))}
        </div>
      </fieldset>
      <button className="primary" type="submit" disabled={isLoading}>
        {isLoading ? 'Planning…' : 'Compare routes'}
      </button>
    </form>
  )
}
