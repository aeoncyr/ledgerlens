// The lender's decision, as the owner sees it at the top of their file: the letter in their
// language, the offer with its schedule, and what they can do next (accept or decline, tick off
// conditions, send the records asked for).
import { useState } from 'react'
import OfferSchedule from '../../components/OfferSchedule.tsx'
import {
  answerOffer,
  markConditionMet,
  sendRequestedRecords,
  type OwnerDecision,
} from '../../decision.ts'
import { rupiah, type Lang, type OwnerStrings } from '../../i18n/owner.ts'
import { errorText, type OwnerEvidence } from '../../owner.ts'
import WhatsAppButton from '../../components/WhatsAppButton.tsx'
import { TickIcon } from './icons.tsx'
import '../../decision.css'

export function WaitingCard({ t }: { t: OwnerStrings }) {
  return (
    <section
      className="ow-card ow-decision ow-decision-waiting"
      aria-labelledby="ow-decision-title"
    >
      <h2 id="ow-decision-title" className="ow-h2">
        {t.waitingTitle}
      </h2>
      <p>{t.waitingText}</p>
    </section>
  )
}

export default function DecisionCard({
  id,
  decision,
  evidence,
  lang,
  t,
}: {
  id: string
  decision: OwnerDecision
  evidence: OwnerEvidence[]
  lang: Lang
  t: OwnerStrings
}) {
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { offer, state } = decision
  const count = (type: string) => evidence.filter((item) => item.type === type).length
  const newRecords = evidence.length - (decision.evidenceCountAtDecision ?? 0)
  // Where the loan officer opens this file.
  const fileUrl = `${window.location.origin}/app/${id}`

  async function act(work: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await work()
      setConfirming(false)
    } catch (e) {
      setError(errorText(e))
    }
    setBusy(false)
  }

  const conditions = decision.conditions ?? []
  const allMet = conditions.length > 0 && conditions.every((c) => c.met)

  return (
    <section
      className={`ow-card ow-decision ow-decision-${decision.action}`}
      aria-labelledby="ow-decision-title"
    >
      <h2 id="ow-decision-title" className="ow-h2">
        {t.decisionTitle[decision.action]}
      </h2>
      <figure className="ow-letter">
        <figcaption className="ow-fine">{t.letterFrom}</figcaption>
        <blockquote lang={lang}>{decision.letter[lang] || decision.letter.en}</blockquote>
      </figure>

      {offer && (
        <>
          <dl className="ow-offer">
            <div className="ow-offer-main">
              <dt>{t.offerInstalment}</dt>
              <dd>{rupiah(offer.instalmentRp)}</dd>
            </div>
            <div>
              <dt>{t.offerAmount}</dt>
              <dd>{rupiah(offer.amountRp)}</dd>
            </div>
            <div>
              <dt>{t.offerMonths}</dt>
              <dd>{t.monthsValue(offer.tenorMonths)}</dd>
            </div>
            <div>
              <dt>{t.offerRate}</dt>
              <dd>{offer.annualRatePct}%</dd>
            </div>
            <div>
              <dt>{t.offerTotal}</dt>
              <dd>{rupiah(offer.totalRp)}</dd>
            </div>
          </dl>
          <OfferSchedule offer={offer} labels={t.schedule} className="ow-schedule" />
          <p className="ow-fine">{t.letterNote}</p>
        </>
      )}

      {decision.action === 'approve' && state === 'offered' && (
        <div className="ow-decision-actions">
          {!confirming ? (
            <>
              <button
                className="ow-button ow-button-wide"
                disabled={busy}
                onClick={() => void act(() => answerOffer(id, true))}
              >
                {busy ? t.answering : t.acceptOffer}
              </button>
              <button
                className="ow-link-button"
                disabled={busy}
                onClick={() => setConfirming(true)}
              >
                {t.declineOffer}
              </button>
            </>
          ) : (
            <div className="ow-confirm" role="alertdialog" aria-labelledby="ow-decline-q">
              <p id="ow-decline-q">{t.declineConfirm}</p>
              <div className="ow-share-actions">
                <button
                  className="ow-button ow-button-danger"
                  disabled={busy}
                  onClick={() => void act(() => answerOffer(id, false))}
                >
                  {busy ? t.answering : t.declineYes}
                </button>
                <button
                  className="ow-button ow-button-quiet"
                  disabled={busy}
                  onClick={() => setConfirming(false)}
                >
                  {t.declineNo}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {state === 'accepted' && (
        <p className="ow-banner ow-decision-answer" role="status">
          <TickIcon size={20} />
          <span>{t.offerAccepted}</span>
        </p>
      )}
      {state === 'accepted' && (
        <WhatsAppButton
          className="ow-button ow-button-whatsapp ow-button-wide"
          label={t.tellOfficer}
          text={t.waAccepted(fileUrl)}
        />
      )}
      {state === 'declined_by_owner' && <p className="ow-fine">{t.offerDeclined}</p>}

      {decision.action === 'approve' && conditions.length > 0 && state !== 'declined_by_owner' && (
        <div className="ow-conditions">
          <h3 className="ow-h3">{t.conditionsTitle}</h3>
          <p className="ow-fine">
            {state === 'accepted' ? t.conditionsLead : t.conditionsAfterAccept}
          </p>
          <ul>
            {conditions.map((condition, index) => {
              const needsRecord =
                !!condition.evidenceType &&
                count(condition.evidenceType) <= (condition.evidenceBefore ?? 0)
              return (
                <li key={index} className={condition.met ? 'ow-condition-met' : undefined}>
                  <span className="ow-condition-mark" aria-hidden="true">
                    {condition.met && <TickIcon size={16} />}
                  </span>
                  <div>
                    <p>{condition.text}</p>
                    {!condition.met && needsRecord && condition.evidenceType && (
                      <p className="ow-fine">
                        {t.conditionNeeds(t.kinds[condition.evidenceType].title)}
                      </p>
                    )}
                    {condition.met && (
                      <WhatsAppButton
                        className="ow-wa-link"
                        label={t.tellOfficer}
                        text={t.waConditionMet(condition.text, fileUrl)}
                      />
                    )}
                  </div>
                  {condition.met ? (
                    <span className="ow-condition-done">{t.conditionMet}</span>
                  ) : (
                    <button
                      className="ow-button ow-button-quiet"
                      disabled={busy || state !== 'accepted' || needsRecord}
                      onClick={() => void act(() => markConditionMet(id, index))}
                    >
                      {t.conditionDone}
                      <span className="visually-hidden">: {condition.text}</span>
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
          {allMet && <p className="ow-fine">{t.allConditionsMet}</p>}
        </div>
      )}

      {decision.action === 'request_more' && (
        <div className="ow-conditions">
          {conditions.length > 0 && (
            <>
              <h3 className="ow-h3">{t.requestedTitle}</h3>
              <ul>
                {conditions.map((condition, index) => (
                  <li key={index}>
                    <span className="ow-condition-mark" aria-hidden="true" />
                    <p>{condition.text}</p>
                  </li>
                ))}
              </ul>
            </>
          )}
          {state === 'requested' ? (
            <>
              <p className="ow-fine">{newRecords > 0 ? t.requestedLead : t.sendNeedsRecords}</p>
              <button
                className="ow-button ow-button-wide"
                disabled={busy || newRecords <= 0}
                onClick={() => void act(() => sendRequestedRecords(id))}
              >
                {busy ? t.answering : t.sendToLender}
              </button>
            </>
          ) : (
            <p className="ow-banner ow-decision-answer" role="status">
              <TickIcon size={20} />
              <span>{t.sentToLender(decision.sentCount ?? newRecords)}</span>
            </p>
          )}
          {state === 'sent' && (
            <WhatsAppButton
              className="ow-button ow-button-whatsapp ow-button-wide"
              label={t.tellOfficer}
              text={t.waRecordsSent(fileUrl)}
            />
          )}
        </div>
      )}

      {error && (
        <p className="ow-error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
