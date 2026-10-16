import { Link } from 'react-router-dom'
import { rupiah, useLang } from '../../i18n/owner.ts'
import { useOwnerFiles, useUid } from '../../owner.ts'
import { SAMPLES } from '../../samples.ts'
import { ArrowIcon, MicIcon, NotebookIcon, QrisIcon, ReceiptIcon } from './icons.tsx'
import OwnerShell from './OwnerShell.tsx'

// /owner: what LedgerLens does for an owner, the way in, and the files they have started.
export default function OwnerHome() {
  const { t } = useLang()
  const uid = useUid()
  const { data: files, loading, error } = useOwnerFiles(uid)

  return (
    <OwnerShell wide>
      <section className="ow-cover" aria-labelledby="ow-home-title">
        <p className="ow-kicker">{t.homeKicker}</p>
        <h1 id="ow-home-title">{t.homeTitle}</h1>
        <p className="ow-cover-lead">{t.homeLead}</p>
        <div className="ow-cover-icons" aria-hidden="true">
          <NotebookIcon size={30} />
          <ReceiptIcon size={30} />
          <QrisIcon size={30} />
          <MicIcon size={30} />
        </div>
      </section>

      <div className="ow-home-grid">
        <section className="ow-section" aria-labelledby="ow-how">
          <h2 id="ow-how" className="ow-h2">
            {t.howTitle}
          </h2>
          <ol className="ow-steps">
            {t.steps.map((step, index) => (
              <li key={index}>
                <span className="ow-step-num" aria-hidden="true">
                  {index + 1}
                </span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
          <Link to="/owner/new" className="ow-button ow-button-wide">
            {t.startFile}
            <ArrowIcon size={20} />
          </Link>
          <p className="ow-fine ow-center">{t.freeNote}</p>
        </section>

        <div>
          <section className="ow-section" aria-labelledby="ow-files">
            <h2 id="ow-files" className="ow-h2">
              {t.myFiles}
            </h2>
            {error && (
              <p className="ow-error" role="alert">
                {t.filesError}: {error}
              </p>
            )}
            {loading && !error && <p className="ow-fine">{t.loading}</p>}
            {!loading && !error && files.length === 0 && <p className="ow-empty">{t.noFiles}</p>}
            {files.length > 0 && (
              <ul className="ow-files">
                {files.map((file) => (
                  <li key={file.id}>
                    <Link to={`/owner/${file.id}`} className="ow-file-link">
                      <span className="ow-file-main">
                        <strong>{file.business.alias}</strong>
                        <span className="ow-fine">
                          {rupiah(file.request.amount)} · {file.request.tenorMonths} {t.monthsUnit}
                        </span>
                      </span>
                      <span className={`ow-pill ow-pill-${file.officerUid ? 'shared' : file.status}`}>
                        {file.officerUid ? t.sharedBanner : (t.status[file.status] ?? file.status)}
                      </span>
                      <ArrowIcon size={18} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <p className="ow-fine">{t.privacyNote}</p>
          </section>

          <section className="ow-section ow-sample-box" aria-labelledby="ow-sample">
            <h2 id="ow-sample" className="ow-h3">
              {t.trySample}
            </h2>
            <p className="ow-fine">{t.trySampleText}</p>
            <ul className="ow-sample-list">
              {SAMPLES.map((s) => (
                <li key={s.slug}>
                  <Link to={`/owner/new?sample=${s.slug}`} className="ow-sample-link">
                    <strong>{s.alias}</strong>
                    <span>
                      {s.businessType}, {s.city}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </OwnerShell>
  )
}
