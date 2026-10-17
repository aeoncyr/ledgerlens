// Words for a lender's invite on the owner's side, in English and Bahasa Indonesia. Kept apart
// from owner.ts; the language is the one the owner chose there (useLang).
import { useLang, type Lang } from './owner.ts'
import type { LenderType } from '../lender.ts'

const EN = {
  kicker: 'An invitation from your lender',
  title: (lender: string) => `${lender} asks you to send your records`,
  lead: (lender: string) =>
    `${lender} uses LedgerLens to look at loan requests from small businesses without a bank statement. You photograph your notebook, supplier receipts and QRIS history on your phone, and LedgerLens checks them against each other for ${lender}.`,
  lenderKind: {
    bpr: 'a rural bank (BPR)',
    bprs: 'an Islamic rural bank (BPRS)',
    cooperative: 'a cooperative (koperasi)',
    microfinance: 'a microfinance institution (LKM)',
    other: 'a lender',
  } as Record<LenderType, string>,
  isA: (lender: string, kind: string) => `${lender} is ${kind}.`,
  whatTitle: 'What happens if you agree',
  what: (lender: string) => [
    `You start a file about your business. It is yours, and only ${lender} can see it.`,
    'You send photos of your records and answer a few questions if something doesn’t match.',
    `${lender} decides on the loan, not LedgerLens. You hear back in this app.`,
    'You can stop sharing or delete the file at any time.',
  ],
  agree: 'I agree, start my file',
  notNow: 'Not now',
  expires: (date: string) => `This invitation works until ${date}, and only once.`,
  fictional: 'LedgerLens is a prototype: use a fictional business, never real records.',
  usedMine: 'You already started a file from this invitation.',
  openMine: 'Open my file',
  used: 'This invitation has already been used to start a file. Ask your lender for a new one.',
  expired: 'This invitation has expired. Invitations work for 14 days; ask your lender for a new one.',
  notFound: 'This invitation link doesn’t work. It may be mistyped; ask your lender to send it again.',
  own: 'This invitation comes from the lender workspace in this browser. To play the business owner, open the link in a private window or on another phone.',
  goHome: 'Go to my files',
  sharedNote: (lender: string) =>
    `This file will be shared with ${lender} as soon as you start it. You can stop sharing at any time.`,
}

type InviteStrings = typeof EN

const ID: InviteStrings = {
  kicker: 'Undangan dari pemberi pinjaman Anda',
  title: (lender) => `${lender} meminta Anda mengirim catatan usaha`,
  lead: (lender) =>
    `${lender} memakai LedgerLens untuk menilai pengajuan pinjaman dari usaha kecil yang tidak punya rekening koran. Anda memotret buku catatan, nota belanja dan riwayat QRIS dengan HP, lalu LedgerLens memeriksanya satu sama lain untuk ${lender}.`,
  lenderKind: {
    bpr: 'bank perekonomian rakyat (BPR)',
    bprs: 'BPR syariah (BPRS)',
    cooperative: 'koperasi',
    microfinance: 'lembaga keuangan mikro (LKM)',
    other: 'pemberi pinjaman',
  },
  isA: (lender, kind) => `${lender} adalah ${kind}.`,
  whatTitle: 'Yang terjadi jika Anda setuju',
  what: (lender) => [
    `Anda membuat berkas tentang usaha Anda. Berkas itu milik Anda, dan hanya ${lender} yang bisa melihatnya.`,
    'Anda mengirim foto catatan dan menjawab beberapa pertanyaan jika ada yang tidak cocok.',
    `${lender} yang memutuskan pinjaman, bukan LedgerLens. Jawabannya muncul di aplikasi ini.`,
    'Anda bisa berhenti berbagi atau menghapus berkas kapan saja.',
  ],
  agree: 'Saya setuju, mulai berkas saya',
  notNow: 'Nanti saja',
  expires: (date) => `Undangan ini berlaku sampai ${date}, dan hanya sekali.`,
  fictional: 'LedgerLens adalah prototipe: gunakan usaha fiktif, jangan catatan asli.',
  usedMine: 'Anda sudah memulai berkas dari undangan ini.',
  openMine: 'Buka berkas saya',
  used: 'Undangan ini sudah dipakai untuk memulai berkas. Minta undangan baru kepada pemberi pinjaman Anda.',
  expired:
    'Undangan ini sudah kedaluwarsa. Undangan berlaku 14 hari; minta yang baru kepada pemberi pinjaman Anda.',
  notFound:
    'Tautan undangan ini tidak berfungsi. Mungkin salah ketik; minta pemberi pinjaman mengirimnya lagi.',
  own: 'Undangan ini berasal dari ruang kerja pemberi pinjaman di browser ini. Untuk berperan sebagai pemilik usaha, buka tautan di jendela pribadi atau di HP lain.',
  goHome: 'Ke berkas saya',
  sharedNote: (lender) =>
    `Berkas ini langsung dibagikan ke ${lender} begitu Anda memulainya. Anda bisa berhenti berbagi kapan saja.`,
}

const STRINGS: Record<Lang, InviteStrings> = { en: EN, id: ID }

export function useInviteStrings() {
  const { lang } = useLang()
  return { lang, it: STRINGS[lang] }
}
