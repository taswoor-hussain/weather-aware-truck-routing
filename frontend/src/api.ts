import type { Place, Plan, PlanInput } from './types'

const GENERIC_ERROR = 'Something went wrong. Please try again.'

async function readError(response: Response): Promise<string> {
  try {
    return firstMessage(await response.json()) ?? GENERIC_ERROR
  } catch {
    return GENERIC_ERROR
  }
}

/** DRF errors are a string, a list, or an object of either, keyed by field. */
function firstMessage(body: unknown): string | undefined {
  if (typeof body === 'string') return body
  if (Array.isArray(body)) return firstMessage(body[0])
  if (body && typeof body === 'object') return firstMessage(Object.values(body)[0])
  return undefined
}

export async function searchPlaces(query: string, signal: AbortSignal): Promise<Place[]> {
  const response = await fetch(`/api/geocode/?q=${encodeURIComponent(query)}`, { signal })
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()).places
}

export async function requestPlan(input: PlanInput, signal: AbortSignal): Promise<Plan> {
  const response = await fetch('/api/plan/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
    signal,
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}
