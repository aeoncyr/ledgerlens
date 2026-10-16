// Records a short spoken answer in the browser. The caller decides what to do with the recording.
import { useEffect, useRef, useState } from 'react'

const MAX_SECONDS = 120

export default function VoiceRecorder({
  label,
  busy = false,
  onRecorded,
}: {
  label: string
  busy?: boolean
  onRecorded: (audio: Blob) => void
}) {
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const [seconds, setSeconds] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (seconds === null) return
    if (seconds >= MAX_SECONDS) {
      recorder.current?.stop()
      return
    }
    const tick = setTimeout(() => setSeconds((s) => (s === null ? s : s + 1)), 1000)
    return () => clearTimeout(tick)
  }, [seconds])

  async function start() {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const media = new MediaRecorder(stream)
      chunks.current = []
      media.ondataavailable = (event) => chunks.current.push(event.data)
      media.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        setSeconds(null)
        onRecorded(new Blob(chunks.current, { type: media.mimeType || 'audio/webm' }))
      }
      recorder.current = media
      media.start()
      setSeconds(0)
    } catch {
      setError('The microphone is not available. Type the answer instead.')
    }
  }

  const recording = seconds !== null
  return (
    <span className="voice">
      <button
        type="button"
        className={`button quiet voice-button ${recording ? 'recording' : ''}`}
        disabled={busy}
        onClick={() => (recording ? recorder.current?.stop() : start())}
        aria-pressed={recording}
      >
        <span className="voice-dot" aria-hidden="true" />
        {recording
          ? `Stop · ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
          : label}
      </button>
      {error && <span className="error">{error}</span>}
    </span>
  )
}
