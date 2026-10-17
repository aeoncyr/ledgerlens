// The policy's stress test: how far monthly sales could fall before an instalment is above the
// largest one the policy allows. The API computes it for new files (api/app/tools/policy.py,
// stored as policy.stressDropPct); files checked before that, and the published samples, don't
// have it, so the same formula runs here from the figures they do store. Code, not the model.
import type { CreditFileData } from './types.ts'

type Policy = CreditFileData['policy']

// Share of net monthly cash flow that may go to repayments (LenderPolicy.max_installment_ratio).
export const MAX_INSTALLMENT_RATIO = 0.3

export const STRESS_ASSUMPTION =
  'Assumes costs move with sales, so net cash flow falls in proportion; the haircut and other debts stay the same.'

/**
 * Whole percent that sales could fall with the instalment still within policy, rounded down;
 * 0 when it is already above the limit or has less than 1% to spare; null with no limit.
 *
 * After a fall d the limit is ratio × capacity × (1 − d) − other debts, and the stored limit is
 * ratio × capacity − other debts, so d = (limit − instalment) / (ratio × capacity).
 */
export function stressDropPct(
  policy: Pick<Policy, 'capacityBasis' | 'maxInstallment'>,
  instalment: number,
): number | null {
  if (policy.capacityBasis === null || policy.maxInstallment === null) return null
  const base = policy.capacityBasis * MAX_INSTALLMENT_RATIO
  const room = policy.maxInstallment - instalment
  if (base <= 0 || room <= 0) return 0
  // The small epsilon keeps an exact 18.0% from flooring to 17 through float error.
  return Math.min(100, Math.floor((room / base) * 100 + 1e-9))
}

/** The stored figure when the file has it, otherwise the same formula run here. */
export function stressOf(policy: Policy): { pct: number | null; computedHere: boolean } {
  if (policy.stressDropPct !== undefined) {
    return { pct: policy.stressDropPct, computedHere: false }
  }
  return { pct: stressDropPct(policy, policy.requestedInstallment), computedHere: true }
}

/** One plain sentence for a stress result. */
export function stressSentence(pct: number | null, within: boolean): string | null {
  if (pct === null) return null
  if (!within) return 'Above the policy limit before any fall in sales.'
  if (pct === 0) return 'At the policy limit already: any fall in sales would take it above.'
  return `Still within policy if sales fall by up to ${pct}%.`
}
