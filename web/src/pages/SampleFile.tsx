// One of the fictional sample files, exactly as the analysis produced it. Static, so it opens
// instantly and costs nothing, whatever the state of Gemini's quota.
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import CreditFile from '../components/CreditFile.tsx'
import SiteNav from '../components/SiteNav.tsx'
import { SAMPLES } from '../samples.ts'
import type { CreditFileData } from '../types.ts'

export default function SampleFile() {
  const { slug } = useParams()
  const known = SAMPLES.some((sample) => sample.slug === slug)
  const [file, setFile] = useState<CreditFileData | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!known) return
    let cancelled = false
    fetch(`/samples/${slug}/file.json`)
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status))
        return response.json() as Promise<CreditFileData>
      })
      .then((data) => !cancelled && setFile(data))
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [slug, known])

  return (
    <>
      <SiteNav />
      <main className="container file-page">
        <p className="crumbs">
          <Link to="/">LedgerLens</Link> / Sample files /{' '}
          {SAMPLES.find((s) => s.slug === slug)?.alias ?? 'Not found'}
        </p>
        {!known && <p>There is no sample file with that name.</p>}
        {known && error && <p>The file could not be loaded. Try again in a moment.</p>}
        {known && !file && !error && <p className="fine">Opening the file…</p>}
        {file && <CreditFile file={file} />}
        <p className="fine disclaimer">
          A fictional business with generated records. LedgerLens recommends; a credit officer
          decides.
        </p>
      </main>
    </>
  )
}
