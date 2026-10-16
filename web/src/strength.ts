// Evidence strength as the officer and the owner see it while collecting: the same points the API
// uses, the evidence grouped by how hard it is, and the one item that would help the file most.
import type { EvidenceType } from './types.ts'

export type Tier = 'hard' | 'medium' | 'soft' | 'physical'

export const TIER_OF: Record<EvidenceType, Tier> = {
  qris_history: 'hard',
  receipt: 'medium',
  ledger_page: 'soft',
  interview_audio: 'soft',
  shop_photo: 'physical',
}

export const TIER_LABEL: Record<Tier, string> = {
  hard: 'Hard',
  medium: 'Medium',
  soft: 'Soft',
  physical: 'Physical',
}

const POINTS: Record<EvidenceType, number> = {
  qris_history: 35,
  receipt: 20,
  ledger_page: 15,
  interview_audio: 10,
  shop_photo: 10,
}

// Four photographed pages stand in for "two months or more" of the notebook while collecting.
const TWO_MONTHS_OF_PAGES = 4

export type NextKey = 'qris' | 'notebook' | 'receipts' | 'more_pages' | 'interview' | 'photo'

export type Strength = {
  score: number
  label: 'Weak' | 'Moderate' | 'Strong'
  tiers: Record<Tier, number>
  // The evidence that would help most next, or null when every kind is on file.
  next: { key: NextKey; type: EvidenceType; text: string } | null
}

export function evidenceStrength(types: EvidenceType[]): Strength {
  const counts = new Map<EvidenceType, number>()
  for (const type of types) counts.set(type, (counts.get(type) ?? 0) + 1)
  const has = (type: EvidenceType) => counts.has(type)
  const pages = counts.get('ledger_page') ?? 0

  const score = Math.min(
    100,
    [...counts.keys()].reduce((sum, type) => sum + POINTS[type], 0) +
      (pages >= TWO_MONTHS_OF_PAGES ? 10 : 0),
  )
  const tiers: Record<Tier, number> = { hard: 0, medium: 0, soft: 0, physical: 0 }
  for (const [type, count] of counts) tiers[TIER_OF[type]] += count

  let next: Strength['next'] = null
  if (!has('qris_history')) {
    next = {
      key: 'qris',
      type: 'qris_history',
      text: 'Add QRIS history: only hard evidence sets the floor of the cash flow.',
    }
  } else if (!has('ledger_page')) {
    next = {
      key: 'notebook',
      type: 'ledger_page',
      text: 'Add notebook pages: they hold the sales and purchases the other sources check.',
    }
  } else if (!has('receipt')) {
    next = {
      key: 'receipts',
      type: 'receipt',
      text: 'Add supplier receipts to check the notebook’s purchases.',
    }
  } else if (pages < TWO_MONTHS_OF_PAGES) {
    next = {
      key: 'more_pages',
      type: 'ledger_page',
      text: 'Add more notebook pages: two months or more is best.',
    }
  } else if (!has('interview_audio')) {
    next = {
      key: 'interview',
      type: 'interview_audio',
      text: 'Record a short interview: the owner’s own words are checked against the books.',
    }
  } else if (!has('shop_photo')) {
    next = { key: 'photo', type: 'shop_photo', text: 'Add a photo of the shop and its stock.' }
  }

  return {
    score,
    label: score >= 70 ? 'Strong' : score >= 40 ? 'Moderate' : 'Weak',
    tiers,
    next,
  }
}
