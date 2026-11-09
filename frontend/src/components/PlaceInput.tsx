import { useEffect, useId, useState } from 'react'
import { searchPlaces } from '../api'
import type { Place } from '../types'

const DEBOUNCE_MS = 250
const MIN_QUERY_LENGTH = 3

interface Props {
  label: string
  placeholder: string
  error?: string
  onChange: (place: Place | null) => void
}

export function PlaceInput({ label, placeholder, error, onChange }: Props) {
  const id = useId()
  const listId = `${id}-list`
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Place[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    if (query.length < MIN_QUERY_LENGTH) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchPlaces(query, controller.signal)
        .then((places) => {
          setResults(places)
          setActiveIndex(0)
          setIsOpen(true)
        })
        .catch(() => setResults([]))
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  function handleType(value: string) {
    setText(value)
    setQuery(value.trim())
    onChange(null)
    if (value.trim().length < MIN_QUERY_LENGTH) {
      setResults([])
      setIsOpen(false)
    }
  }

  function choose(place: Place) {
    setText(place.label)
    setQuery('')
    setResults([])
    setIsOpen(false)
    onChange(place)
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (!isOpen || results.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => (index - 1 + results.length) % results.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      choose(results[activeIndex])
    } else if (event.key === 'Escape') {
      setIsOpen(false)
    }
  }

  return (
    <div className="field place-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        role="combobox"
        aria-expanded={isOpen}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={Boolean(error)}
        autoComplete="off"
        placeholder={placeholder}
        value={text}
        onChange={(event) => handleType(event.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => setIsOpen(false)}
      />
      {isOpen && results.length > 0 && (
        <ul id={listId} role="listbox" className="suggestions">
          {results.map((place, index) => (
            <li
              key={place.label}
              role="option"
              aria-selected={index === activeIndex}
              className={index === activeIndex ? 'active' : undefined}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(place)}
              onMouseEnter={() => setActiveIndex(index)}
            >
              {place.label}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="field-error">{error}</p>}
    </div>
  )
}
