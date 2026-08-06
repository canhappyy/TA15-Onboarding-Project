import { useState, useEffect } from "react"

interface GeolocationOptions {
  enableHighAccuracy?: boolean
  timeout?: number
  maximumAge?: number
}

export function useGeolocation(
  defaultPosition: [number, number],
  options: GeolocationOptions = {
    enableHighAccuracy: true,
    timeout: 8000,
    maximumAge: 0,
  }
) {
  const [position, setPosition] = useState<[number, number]>(defaultPosition)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(true)

  useEffect(() => {
    let isMounted = true

    if (typeof window === "undefined" || !("geolocation" in navigator)) {
      const timer = setTimeout(() => {
        if (isMounted) {
          setError("Geolocation is not supported by this browser.")
          setLoading(false)
        }
      }, 0)
      return () => {
        isMounted = false
        clearTimeout(timer)
      }
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (isMounted) {
          setPosition([pos.coords.latitude, pos.coords.longitude])
          setError(null)
          setLoading(false)
        }
      },
      (err) => {
        if (isMounted) {
          setError(err.message)
          setLoading(false)
          console.warn("Geolocation access denied or failed:", err.message)
        }
      },
      options
    )

    return () => {
      isMounted = false
    }
  }, [])

  return { position, error, loading }
}
