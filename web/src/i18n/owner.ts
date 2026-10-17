// Words for the business owner's pages, in English and Bahasa Indonesia. The choice is remembered in
// this browser and shared by every owner page through a tiny store; until one is made, the
// browser's language decides (see readStored).
import { useSyncExternalStore } from 'react'

export type Lang = 'en' | 'id'

const STORAGE_KEY = 'ledgerlens-owner-lang'

// A choice made in this browser wins. Before one is made, a phone or browser set to Indonesian
// opens the owner pages in Bahasa Indonesia, and every other one in English.
function readStored(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'id' || stored === 'en') return stored
  } catch {
    // Storage can be blocked (private windows); fall back to the browser's language.
  }
  return prefersBahasa(typeof navigator === 'undefined' ? '' : navigator.language) ? 'id' : 'en'
}

/** True for "id" and "id-ID", the languages an Indonesian phone reports. */
export function prefersBahasa(language: string | undefined): boolean {
  return /^id(-|$)/i.test(language ?? '')
}

let current: Lang = readStored()
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function setLang(lang: Lang) {
  current = lang
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Private windows can block storage; the choice then lasts until the page reloads.
  }
  document.documentElement.lang = lang
  for (const listener of listeners) listener()
}

const rupiahFormat = new Intl.NumberFormat('id-ID')
export const rupiah = (value: number) => `Rp ${rupiahFormat.format(Math.round(value || 0))}`

const EN = {
  langName: 'English',
  switchTo: 'Bahasa Indonesia',
  switchLabel: 'Baca dalam Bahasa Indonesia',
  appName: 'Business owner app',
  home: 'Home',
  prototype: 'Prototype: fictional businesses only. Please don’t upload real records.',
  loading: 'Loading…',
  somethingWrong: 'Something went wrong',
  tryAgain: 'Try again',
  back: 'Back',

  // Home
  homeKicker: 'For warung, tailors, food stalls and other small businesses',
  homeTitle: 'Show a lender what your notebook already proves.',
  homeLead:
    'No bank statement? Your handwritten book, supplier receipts and QRIS history are evidence too. Send us photos and we turn them into a checked file you can share with a lender.',
  howTitle: 'How it works',
  steps: [
    {
      title: 'Send photos of your records',
      text: 'Notebook pages, supplier receipts, your QRIS history and a short voice note. Your phone camera is enough.',
    },
    {
      title: 'We check them against each other',
      text: 'Each record is read and compared with the others. You see what was confirmed and what is still missing.',
    },
    {
      title: 'Share a checked file with a lender',
      text: 'You decide who sees it. Send a link or a code to your lender, and stop sharing whenever you want.',
    },
  ],
  startFile: 'Start my file',
  freeNote: 'Free, takes about five minutes. No account or password.',
  trySample: 'Try with a sample business',
  trySampleText:
    'No notebook to hand? Use one of these fictional businesses. You can add its photographed records in one tap.',
  myFiles: 'My files',
  noFiles: 'You haven’t started a file yet.',
  openFile: 'Open',
  filesError: 'Could not load your files',
  privacyNote:
    'Your files are linked to this browser only. Anyone else sees them only if you share them.',

  // New file
  newTitle: 'Tell us about your business',
  newLead: 'A few short questions about your business and the loan you need.',
  sampleUsed: (alias: string) => `Filled in with the sample business “${alias}”.`,
  aliasLabel: 'Business name',
  aliasHint: 'The name customers know, like “Warung Bu Sari”. Never your legal name or NIK.',
  aliasPlaceholder: 'Warung Bu Sari',
  typeLabel: 'What do you sell or do?',
  typePlaceholder: 'Grocery stall (warung sembako)',
  typeSuggestions: [
    'Grocery stall (warung sembako)',
    'Food stall (warung makan)',
    'Tailor (penjahit)',
    'Motorbike repair (bengkel)',
    'Coffee stall (warung kopi)',
    'Phone credit and top-ups (konter pulsa)',
  ],
  cityLabel: 'City',
  cityPlaceholder: 'Bekasi',
  yearsLabel: 'Years in business',
  amountLabel: 'How much would you like to borrow?',
  amountHint: 'In rupiah.',
  tenorLabel: 'Over how many months?',
  monthsUnit: 'months',
  otherDebtsLabel: 'Other loan instalments you pay each month (optional)',
  otherDebtsHint:
    'Include online loans (pinjol), koperasi, leasing and family loans. Leave 0 if none. Being honest here helps: the lender sees what you can safely repay.',
  createButton: 'Continue',
  creating: 'Starting your file…',

  // File: header and stages
  fileNotFound: 'We can’t find this file',
  fileNotFoundText:
    'It may belong to another browser, or the link is incomplete. Files are linked to the browser that started them.',
  backHome: 'Back to my files',
  requestLine: (amount: string, months: number) => `Asking for ${amount} over ${months} months`,
  stageAgree: 'Agree',
  stageSend: 'Send records',
  stageCheck: 'Check',
  stageShare: 'Share',
  progressLabel: 'Your progress',
  sharedBanner: 'Shared with a lender',
  sharedBannerText: 'A loan officer has opened your file. They can see your records and answers.',

  // Consent
  consentTitle: 'Before you send anything',
  consentWho:
    'Only you can see this file, until you share it. When you share it, the lender’s loan officer who opens your link sees your records, what was checked and your answers.',
  consentWhere:
    'Your details are stored in Google Cloud in Jakarta. Photos and voice notes are stored in the United States. Their contents are read by Gemini, Google’s AI, to check them.',
  consentDecide:
    'The check helps a lender understand your business; it does not decide. A person at the lender always makes the decision.',
  consentWithdraw: 'You can stop sharing or withdraw your agreement at any time.',
  consentMore: 'How LedgerLens protects your data',
  consentButton: 'I agree, let’s start',
  consentNotNow: 'Not now',
  consentSaving: 'Saving…',

  // Evidence
  sendTitle: 'Send photos of your records',
  moreTitle: 'Your records',
  nextBestLabel: 'Most helpful next',
  nextBest: {
    qris: 'Add your QRIS history: it is the only record that proves your sales for certain.',
    notebook: 'Add your notebook pages: they show the sales and purchases the other records check.',
    receipts: 'Add supplier receipts: they confirm the purchases in your notebook.',
    more_pages: 'Add more notebook pages: two months or more is best.',
    interview: 'Record a short voice note: what you say is checked against your records.',
    photo: 'Add a photo of your shop and its stock.',
  },
  moreLead: 'Add more at any time, then check again. The tips above show what helps most.',
  sendLead:
    'Tap a box to open your camera. The more kinds you send, the stronger your file. Two months of records is best.',
  kinds: {
    ledger_page: {
      title: 'Notebook pages',
      hint: 'One photo per page, flat, in good light.',
      action: 'Take a photo',
    },
    receipt: {
      title: 'Supplier receipts',
      hint: 'Notas for the stock you buy.',
      action: 'Take a photo',
    },
    qris_history: {
      title: 'QRIS history',
      hint: 'Screenshots from your merchant app, one per month.',
      action: 'Choose screenshots',
    },
    interview_audio: {
      title: 'Voice note',
      hint: 'One or two minutes: what you sell, a normal day’s sales, what the loan is for.',
      action: 'Record',
    },
    shop_photo: {
      title: 'Shop photo',
      hint: 'The front of your shop and your shelves.',
      action: 'Take a photo',
    },
  },
  countSent: (n: number) => (n === 0 ? 'None yet' : n === 1 ? '1 sent' : `${n} sent`),
  fromGallery: 'or choose from gallery',
  fromFiles: 'or choose a file',
  visitNote:
    'A loan officer may confirm some items when they visit you, for example your QRIS history in the app itself. That is normal, and it makes your file stronger.',
  sentTitle: 'What you have sent',
  sentNone: 'Nothing yet. Start with your notebook pages.',
  sentByOfficer: 'added by the loan officer',
  sampleTitle: 'Trying it out?',
  sampleText:
    'Add the photographed records of a fictional business: notebook pages, receipts, QRIS screenshots and a voice note.',
  sampleButton: 'Add these sample records',
  uploading: (i: number, n: number) => `Sending ${i} of ${n}…`,
  fetchingSample: 'Getting the sample records…',
  tooBig: (name: string) => `“${name}” is larger than 15 MB. Please send a smaller photo.`,
  wrongType: (name: string) => `“${name}” is not a photo or a recording.`,

  // Check
  checkButton: (n: number) => `Check my records (${n})`,
  checkNeedsRecords: 'Send at least one record to start the check.',
  checkAgainAll: 'Check all my records again',
  checkingTitle: 'Checking your records',
  checkingLead:
    'Each record is read and compared with the others. This usually takes one to three minutes. You can keep this page open.',
  checkingStarting: 'Starting…',
  agents: {
    intake: 'Getting your records ready',
    ledger_reader: 'Reading your notebook pages',
    receipt_reader: 'Reading your receipts',
    qris_reader: 'Reading your QRIS history',
    photo_assessor: 'Looking at your shop photos',
    interview_listener: 'Listening to your voice note',
    calculator: 'Adding up the numbers',
    verifier: 'Comparing your records with each other',
    policy: 'Preparing the file for a lender',
    memo_writer: 'Writing your summary',
  } as Record<string, string>,
  stepDone: 'Done',
  stepWorking: 'Working',
  stepFailed: 'Problem',
  stepNext: 'Waiting',
  checkFailed:
    'The check stopped before it finished, usually because Gemini was busy. Nothing you sent is lost: check again in a minute.',
  checkQuota:
    'Today’s free checking capacity is used up. It comes back in the early afternoon, Jakarta time, and your records are saved.',

  // Summary
  summaryTitle: 'Your summary',
  summaryLead: 'Written for you, from the records you sent.',
  confirmedTitle: 'What we could confirm',
  missingTitle: 'What’s still missing',
  tipsTitle: 'Tips to make your file stronger',
  summaryPending: 'Your summary will appear here after the check.',
  questionsTitle: 'A few questions for you',
  questionsLead:
    'Some records didn’t quite match. A short answer in your own words helps the lender understand.',
  questionOriginal: 'In Bahasa Indonesia:',
  answerLabel: (n: number) => `Your answer to question ${n}`,
  answerPlaceholder: 'For example: In September I also sold at the market on weekends.',
  answered: 'Your answer',
  recordAnswer: 'Answer by voice',
  declineAnswer: 'I prefer not to answer',
  declinedNote: 'You preferred not to answer. That is fine and is recorded neutrally.',
  sendingVoice: 'Sending your voice answer…',
  voiceSent: 'Received. Your words were written down for the lender.',
  recheckButton: 'Check again with my answers',
  recheckNeedsAnswer: 'Write at least one answer first.',
  savingAnswers: 'Saving your answers…',

  // Share
  shareTitle: 'Share with a lender',
  shareLead:
    'Send this link to the loan officer at your bank, koperasi or BPR. They see your records and what was checked. You can stop sharing at any time.',
  shareButton: 'Create my share link',
  shareSeesTitle: 'The loan officer will see',
  shareSees: [
    'Your notebook pages, receipts, QRIS screenshots, photos and interview',
    'What LedgerLens read from them, and what it checked',
    'Your answers to the questions',
    'Your monthly cash flow and the largest instalment it supports',
  ],
  shareNotTitle: 'They will not see',
  shareNot: [
    'Your legal name or ID number: we never ask for them',
    'Your other files',
    'Anything at all once you stop sharing',
  ],
  shareOneLender: 'One lender at a time: the first loan officer to open your link holds the file.',
  sharing: 'Creating…',
  shareLinkLabel: 'Your share link',
  shareCodeLabel: 'Or read out this code',
  copy: 'Copy link',
  copied: 'Copied',
  whatsapp: 'Send on WhatsApp',
  tellOfficer: 'Tell my loan officer on WhatsApp',
  waAccepted: (url: string) =>
    `Hello, I have accepted the loan offer for my business on LedgerLens. My file: ${url}`,
  waConditionMet: (text: string, url: string) =>
    `Hello, I have done what you asked before the loan: "${text}". My file on LedgerLens: ${url}`,
  waRecordsSent: (url: string) =>
    `Hello, I have sent the records you asked for on LedgerLens. My file: ${url}`,
  whatsappText: (url: string, code: string) =>
    `Hello, here is the credit file for my business on LedgerLens. It shows my records and what was checked. Open: ${url} (code ${code})`,
  stopSharing: 'Stop sharing',
  stopConfirm: 'The lender will lose access to your file. Stop sharing?',
  stopYes: 'Yes, stop sharing',
  stopNo: 'Keep sharing',
  stopping: 'Stopping…',

  // Who has seen my file: the owner's timeline (api/app/routers/activity.py)
  activityTitle: 'Who has seen your file',
  activityLead:
    'Each time a lender opens your file or decides on it, it shows here. The lender’s staff names and their notes are not shown here.',
  activityEmpty: 'Nothing has happened to your file yet.',
  activityFailed: 'We couldn’t load this list just now. It will try again when the page reloads.',
  activityTimes: (n: number) => `${n} times`,
  activityEvents: {
    started: 'You started this file',
    started_by_lender: 'A loan officer started this file',
    invited: 'A lender invited you to send your records',
    invite_opened: 'You opened the lender’s invitation',
    consent_given: 'You agreed to the check',
    consent_withdrawn: 'You withdrew your agreement',
    checked: 'Your records were checked',
    checked_again: 'Your file was checked again with your answers',
    shared: 'You made a share link',
    opened_by_lender: 'A lender opened your file',
    share_stopped: 'You stopped sharing; the lender can no longer open your file',
    decision_recommended: 'A loan officer recommended a decision',
    signoff_opened: 'A second person at the lender began checking the decision',
    decision_reconsidered: 'The lender is looking at the decision again',
    signed_off: 'A second person at the lender signed off the decision',
    sent_to_you: 'The lender’s decision was sent to you',
    offer_accepted: 'You accepted the offer',
    offer_declined: 'You declined the offer',
    condition_met: 'A condition was marked as met',
    records_sent: 'You sent the records the lender asked for',
  } as Record<string, string>,
  shareNeedsCheck: 'Check your records first, then you can share the file.',

  // The lender's decision
  waitingTitle: 'Your lender is deciding',
  waitingText:
    'A loan officer has made a recommendation, and a second person at the lender is checking it. The decision will appear here.',
  decisionTitle: {
    approve: 'Your loan offer',
    decline: 'Your lender’s decision',
    request_more: 'Your lender asks for more records',
  } as Record<string, string>,
  letterFrom: 'From your lender',
  letterNote: 'The amounts are calculated from the offer, not written by AI.',
  offerAmount: 'Loan',
  offerInstalment: 'Each month',
  offerMonths: 'For',
  monthsValue: (n: number) => `${n} months`,
  offerRate: 'Interest a year',
  offerTotal: 'Total you repay',
  schedule: {
    summary: 'See every month',
    caption: 'What you pay each month, the interest in it, and what you still owe after it.',
    month: 'Month',
    instalment: 'Payment',
    interest: 'Interest',
    principal: 'Loan repaid',
    balance: 'Still owed',
  },
  acceptOffer: 'Accept the offer',
  declineOffer: 'Decline the offer',
  declineConfirm: 'Decline this offer? Your lender will be told. Your file stays yours.',
  declineYes: 'Yes, decline',
  declineNo: 'Go back',
  answering: 'Sending…',
  offerAccepted: 'You accepted the offer. Your lender will contact you about the next steps.',
  offerDeclined: 'You declined the offer. Your lender has been told.',
  conditionsTitle: 'Before the money is paid out',
  conditionsLead:
    'Your lender asks for these. When one needs a record, send it under Your records below, then tap Done.',
  conditionsAfterAccept: 'Accept the offer first, then tick these off.',
  conditionDone: 'Done',
  conditionMet: 'Done',
  conditionNeeds: (kind: string) => `This needs a new record (${kind}). Send it under Your records first.`,
  allConditionsMet: 'Everything your lender asked for is done.',
  requestedTitle: 'What your lender asks for',
  requestedLead:
    'Nothing has been decided yet. Add these under Your records below, then tell your lender.',
  sendToLender: 'Send to my lender',
  sendNeedsRecords: 'Add at least one new record below first.',
  sentToLender: (n: number) =>
    `Sent. Your lender knows you added ${n === 1 ? 'one new record' : `${n} new records`}.`,
  checkLocked:
    'Your lender is deciding on the file as it is now, so it can’t be checked again. You can still send the records your lender asks for.',

  // Remind me to check again
  remindButton: 'Remind me to check again',
  remindLead:
    'Collect a few more weeks of records, then check again. Add a reminder to your Google Calendar for 30 days from now, with these tips in it.',
  remindLeadDeclined:
    'This decision is about your file as it is today. With a few more weeks of records it can be stronger: add a reminder to your Google Calendar for 30 days from now, with the tips from your summary.',
  remindEventTitle: 'Check my LedgerLens file again',
  remindDetails: (tips: string[], url: string) =>
    [
      'Time to look at your LedgerLens file again: add the records you have collected since your last check, then check again.',
      '',
      ...(tips.length ? ['Tips from your last check:', ...tips.map((tip) => `• ${tip}`), ''] : []),
      `Your file (open it in the same browser as before): ${url}`,
    ].join('\n'),
  opensCalendar: ' (opens Google Calendar in a new tab)',

  // Delete my file
  deleteTitle: 'Delete my file',
  deleteLead:
    'You can delete this file and everything in it at any time: photos, recordings, answers, your summary and any share link. Indonesia’s personal data protection law (UU PDP) gives you that right.',
  deleteButton: 'Delete my file',
  deleteConfirm:
    'Delete this file for good? Every photo, recording and answer is removed, and a lender you shared it with loses it too. This can’t be undone.',
  deleteYes: 'Yes, delete everything',
  deleteNo: 'Keep my file',
  deleting: 'Deleting…',
  deleteBlockedDeciding:
    'Your lender is deciding on this file right now, so it can’t be deleted yet. You can delete it once they have decided.',
  deleteBlockedAccepted:
    'You accepted a loan offer on this file, so your lender needs to keep it while the loan is arranged. Ask your lender if you want it removed.',
  deleteBlockedChecking: 'Your records are being checked. Wait for the check to finish, then you can delete the file.',

  status: {
    draft: 'Needs your agreement',
    collecting: 'Sending records',
    analyzing: 'Being checked',
    needs_follow_up: 'Questions for you',
    ready: 'Checked',
    in_review: 'With the lender',
    awaiting_signoff: 'The lender is deciding',
    decided: 'The lender has decided',
  } as Record<string, string>,
}

export type OwnerStrings = typeof EN

const ID: OwnerStrings = {
  langName: 'Bahasa Indonesia',
  switchTo: 'English',
  switchLabel: 'Read in English',
  appName: 'Aplikasi pemilik usaha',
  home: 'Beranda',
  prototype: 'Prototipe: hanya untuk usaha fiktif. Jangan unggah catatan asli.',
  loading: 'Memuat…',
  somethingWrong: 'Ada yang salah',
  tryAgain: 'Coba lagi',
  back: 'Kembali',

  homeKicker: 'Untuk warung, penjahit, warung makan dan usaha kecil lainnya',
  homeTitle: 'Tunjukkan kepada pemberi pinjaman apa yang sudah dibuktikan buku catatan Anda.',
  homeLead:
    'Tidak punya rekening koran? Buku catatan, nota belanja dan riwayat QRIS Anda juga bukti. Kirim fotonya, kami jadikan berkas yang sudah diperiksa dan bisa Anda bagikan ke pemberi pinjaman.',
  howTitle: 'Cara kerjanya',
  steps: [
    {
      title: 'Kirim foto catatan Anda',
      text: 'Halaman buku catatan, nota belanja, riwayat QRIS dan pesan suara singkat. Kamera HP sudah cukup.',
    },
    {
      title: 'Kami periksa satu sama lain',
      text: 'Setiap catatan dibaca dan dibandingkan dengan yang lain. Anda melihat apa yang terkonfirmasi dan apa yang masih kurang.',
    },
    {
      title: 'Bagikan berkas ke pemberi pinjaman',
      text: 'Anda yang menentukan siapa yang melihatnya. Kirim tautan atau kode, dan berhenti berbagi kapan saja.',
    },
  ],
  startFile: 'Mulai berkas saya',
  freeNote: 'Gratis, sekitar lima menit. Tanpa akun atau kata sandi.',
  trySample: 'Coba dengan usaha contoh',
  trySampleText:
    'Tidak sedang memegang buku catatan? Pakai salah satu usaha fiktif ini. Foto catatannya bisa ditambahkan dengan satu ketukan.',
  myFiles: 'Berkas saya',
  noFiles: 'Anda belum memulai berkas.',
  openFile: 'Buka',
  filesError: 'Berkas Anda tidak dapat dimuat',
  privacyNote:
    'Berkas Anda hanya terhubung ke peramban ini. Orang lain hanya bisa melihatnya jika Anda membagikannya.',

  newTitle: 'Ceritakan tentang usaha Anda',
  newLead: 'Beberapa pertanyaan singkat tentang usaha Anda dan pinjaman yang Anda butuhkan.',
  sampleUsed: (alias: string) => `Diisi dengan usaha contoh “${alias}”.`,
  aliasLabel: 'Nama usaha',
  aliasHint: 'Nama yang dikenal pelanggan, misalnya “Warung Bu Sari”. Jangan nama asli atau NIK Anda.',
  aliasPlaceholder: 'Warung Bu Sari',
  typeLabel: 'Apa yang Anda jual atau kerjakan?',
  typePlaceholder: 'Warung sembako',
  typeSuggestions: [
    'Warung sembako',
    'Warung makan',
    'Penjahit',
    'Bengkel motor',
    'Warung kopi',
    'Konter pulsa',
  ],
  cityLabel: 'Kota',
  cityPlaceholder: 'Bekasi',
  yearsLabel: 'Lama usaha (tahun)',
  amountLabel: 'Berapa yang ingin Anda pinjam?',
  amountHint: 'Dalam rupiah.',
  tenorLabel: 'Untuk berapa bulan?',
  monthsUnit: 'bulan',
  otherDebtsLabel: 'Cicilan pinjaman lain yang Anda bayar setiap bulan (boleh dikosongkan)',
  otherDebtsHint:
    'Termasuk pinjaman online (pinjol), koperasi, leasing dan pinjaman keluarga. Isi 0 jika tidak ada. Jujur di sini membantu: pemberi pinjaman melihat cicilan yang aman untuk Anda.',
  createButton: 'Lanjut',
  creating: 'Memulai berkas Anda…',

  fileNotFound: 'Berkas ini tidak ditemukan',
  fileNotFoundText:
    'Mungkin berkas ini milik peramban lain, atau tautannya tidak lengkap. Berkas terhubung ke peramban yang memulainya.',
  backHome: 'Kembali ke berkas saya',
  requestLine: (amount: string, months: number) => `Mengajukan ${amount} untuk ${months} bulan`,
  stageAgree: 'Setuju',
  stageSend: 'Kirim catatan',
  stageCheck: 'Periksa',
  stageShare: 'Bagikan',
  progressLabel: 'Kemajuan Anda',
  sharedBanner: 'Sudah dibagikan ke pemberi pinjaman',
  sharedBannerText:
    'Petugas kredit sudah membuka berkas Anda. Mereka bisa melihat catatan dan jawaban Anda.',

  consentTitle: 'Sebelum Anda mengirim apa pun',
  consentWho:
    'Hanya Anda yang bisa melihat berkas ini, sampai Anda membagikannya. Setelah dibagikan, petugas kredit yang membuka tautan Anda bisa melihat catatan Anda, hasil pemeriksaan dan jawaban Anda.',
  consentWhere:
    'Data Anda disimpan di Google Cloud di Jakarta. Foto dan pesan suara disimpan di Amerika Serikat. Isinya dibaca oleh Gemini, kecerdasan buatan milik Google, untuk diperiksa.',
  consentDecide:
    'Pemeriksaan ini membantu pemberi pinjaman memahami usaha Anda; bukan yang memutuskan. Keputusan selalu diambil oleh petugas di lembaga pemberi pinjaman.',
  consentWithdraw: 'Anda boleh berhenti berbagi atau menarik persetujuan kapan saja.',
  consentMore: 'Cara LedgerLens melindungi data Anda (dalam bahasa Inggris)',
  consentButton: 'Saya setuju, mulai',
  consentNotNow: 'Nanti saja',
  consentSaving: 'Menyimpan…',

  sendTitle: 'Kirim foto catatan Anda',
  moreTitle: 'Catatan Anda',
  nextBestLabel: 'Paling membantu berikutnya',
  nextBest: {
    qris: 'Tambahkan riwayat QRIS: hanya catatan ini yang membuktikan penjualan Anda dengan pasti.',
    notebook: 'Tambahkan foto buku catatan: isinya penjualan dan pembelian yang dicocokkan dengan bukti lain.',
    receipts: 'Tambahkan nota pemasok: nota memastikan pembelian di buku catatan Anda.',
    more_pages: 'Tambahkan halaman buku catatan lagi: dua bulan atau lebih paling baik.',
    interview: 'Rekam pesan suara singkat: cerita Anda dicocokkan dengan catatan.',
    photo: 'Tambahkan foto toko dan stok barang Anda.',
  },
  moreLead: 'Tambahkan kapan saja, lalu periksa ulang. Saran di atas menunjukkan yang paling membantu.',
  sendLead:
    'Ketuk kotak untuk membuka kamera. Semakin banyak jenis yang Anda kirim, semakin kuat berkas Anda. Catatan dua bulan paling baik.',
  kinds: {
    ledger_page: {
      title: 'Halaman buku catatan',
      hint: 'Satu foto per halaman, rata, cahaya terang.',
      action: 'Ambil foto',
    },
    receipt: {
      title: 'Nota belanja',
      hint: 'Nota dari pemasok untuk barang yang Anda beli.',
      action: 'Ambil foto',
    },
    qris_history: {
      title: 'Riwayat QRIS',
      hint: 'Tangkapan layar dari aplikasi merchant, satu per bulan.',
      action: 'Pilih tangkapan layar',
    },
    interview_audio: {
      title: 'Pesan suara',
      hint: 'Satu atau dua menit: apa yang Anda jual, penjualan sehari biasa, untuk apa pinjamannya.',
      action: 'Rekam',
    },
    shop_photo: {
      title: 'Foto tempat usaha',
      hint: 'Bagian depan toko dan rak barang Anda.',
      action: 'Ambil foto',
    },
  },
  countSent: (n: number) => (n === 0 ? 'Belum ada' : `${n} terkirim`),
  fromGallery: 'atau pilih dari galeri',
  fromFiles: 'atau pilih berkas',
  visitNote:
    'Petugas kredit mungkin akan memastikan beberapa hal saat berkunjung, misalnya riwayat QRIS langsung di aplikasinya. Itu wajar, dan membuat berkas Anda lebih kuat.',
  sentTitle: 'Yang sudah Anda kirim',
  sentNone: 'Belum ada. Mulailah dengan halaman buku catatan.',
  sentByOfficer: 'ditambahkan oleh petugas kredit',
  sampleTitle: 'Sekadar mencoba?',
  sampleText:
    'Tambahkan foto catatan usaha fiktif: halaman buku catatan, nota, tangkapan layar QRIS dan pesan suara.',
  sampleButton: 'Tambahkan catatan contoh ini',
  uploading: (i: number, n: number) => `Mengirim ${i} dari ${n}…`,
  fetchingSample: 'Mengambil catatan contoh…',
  tooBig: (name: string) => `“${name}” lebih dari 15 MB. Kirim foto yang lebih kecil.`,
  wrongType: (name: string) => `“${name}” bukan foto atau rekaman.`,

  checkButton: (n: number) => `Periksa catatan saya (${n})`,
  checkNeedsRecords: 'Kirim setidaknya satu catatan untuk mulai memeriksa.',
  checkAgainAll: 'Periksa ulang semua catatan saya',
  checkingTitle: 'Memeriksa catatan Anda',
  checkingLead:
    'Setiap catatan dibaca dan dibandingkan dengan yang lain. Biasanya satu sampai tiga menit. Biarkan halaman ini terbuka.',
  checkingStarting: 'Memulai…',
  agents: {
    intake: 'Menyiapkan catatan Anda',
    ledger_reader: 'Membaca halaman buku catatan',
    receipt_reader: 'Membaca nota belanja',
    qris_reader: 'Membaca riwayat QRIS',
    photo_assessor: 'Melihat foto tempat usaha',
    interview_listener: 'Mendengarkan pesan suara',
    calculator: 'Menjumlahkan angka',
    verifier: 'Membandingkan catatan satu sama lain',
    policy: 'Menyiapkan berkas untuk pemberi pinjaman',
    memo_writer: 'Menulis ringkasan Anda',
  },
  stepDone: 'Selesai',
  stepWorking: 'Sedang berjalan',
  stepFailed: 'Bermasalah',
  stepNext: 'Menunggu',
  checkFailed:
    'Pemeriksaan berhenti sebelum selesai, biasanya karena Gemini sedang sibuk. Tidak ada yang hilang: periksa lagi sebentar lagi.',
  checkQuota:
    'Kapasitas pemeriksaan gratis hari ini sudah habis. Tersedia lagi siang hari waktu Jakarta, dan catatan Anda tetap tersimpan.',

  summaryTitle: 'Ringkasan Anda',
  summaryLead: 'Ditulis untuk Anda, dari catatan yang Anda kirim.',
  confirmedTitle: 'Yang sudah terkonfirmasi',
  missingTitle: 'Yang masih kurang',
  tipsTitle: 'Saran agar berkas Anda lebih kuat',
  summaryPending: 'Ringkasan akan muncul di sini setelah pemeriksaan.',
  questionsTitle: 'Beberapa pertanyaan untuk Anda',
  questionsLead:
    'Ada catatan yang kurang cocok. Jawaban singkat dengan kata-kata Anda sendiri membantu pemberi pinjaman memahami.',
  questionOriginal: 'Dalam Bahasa Indonesia:',
  answerLabel: (n: number) => `Jawaban Anda untuk pertanyaan ${n}`,
  answerPlaceholder: 'Misalnya: Bulan September saya juga berjualan di pasar setiap akhir pekan.',
  answered: 'Jawaban Anda',
  recordAnswer: 'Jawab dengan suara',
  declineAnswer: 'Saya memilih tidak menjawab',
  declinedNote: 'Anda memilih tidak menjawab. Itu tidak apa-apa dan dicatat secara netral.',
  sendingVoice: 'Mengirim jawaban suara Anda…',
  voiceSent: 'Diterima. Kata-kata Anda sudah dituliskan untuk pemberi pinjaman.',
  recheckButton: 'Periksa ulang dengan jawaban saya',
  recheckNeedsAnswer: 'Tulis setidaknya satu jawaban dulu.',
  savingAnswers: 'Menyimpan jawaban Anda…',

  shareTitle: 'Bagikan ke pemberi pinjaman',
  shareLead:
    'Kirim tautan ini ke petugas kredit di bank, koperasi atau BPR Anda. Mereka melihat catatan Anda dan hasil pemeriksaannya. Anda bisa berhenti berbagi kapan saja.',
  shareButton: 'Buat tautan berbagi',
  shareSeesTitle: 'Yang akan dilihat petugas kredit',
  shareSees: [
    'Foto buku catatan, nota, tangkapan layar QRIS, foto usaha dan wawancara Anda',
    'Apa yang dibaca LedgerLens dari semua itu, dan apa yang diperiksa',
    'Jawaban Anda atas pertanyaan',
    'Arus kas bulanan Anda dan cicilan terbesar yang sanggup ditanggung',
  ],
  shareNotTitle: 'Yang tidak akan mereka lihat',
  shareNot: [
    'Nama lengkap atau NIK Anda: kami tidak pernah memintanya',
    'Berkas Anda yang lain',
    'Apa pun setelah Anda berhenti berbagi',
  ],
  shareOneLender: 'Satu pemberi pinjaman sekaligus: petugas kredit pertama yang membuka tautan Anda memegang berkasnya.',
  sharing: 'Membuat…',
  shareLinkLabel: 'Tautan berbagi Anda',
  shareCodeLabel: 'Atau bacakan kode ini',
  copy: 'Salin tautan',
  copied: 'Tersalin',
  whatsapp: 'Kirim lewat WhatsApp',
  tellOfficer: 'Kabari petugas kredit lewat WhatsApp',
  waAccepted: (url: string) =>
    `Halo, saya sudah menerima tawaran pinjaman untuk usaha saya di LedgerLens. Berkas saya: ${url}`,
  waConditionMet: (text: string, url: string) =>
    `Halo, saya sudah memenuhi syarat sebelum pencairan: "${text}". Berkas saya di LedgerLens: ${url}`,
  waRecordsSent: (url: string) =>
    `Halo, saya sudah mengirim catatan yang Bapak/Ibu minta di LedgerLens. Berkas saya: ${url}`,
  whatsappText: (url: string, code: string) =>
    `Halo, ini berkas kredit usaha saya di LedgerLens. Isinya catatan saya dan hasil pemeriksaannya. Buka: ${url} (kode ${code})`,
  stopSharing: 'Berhenti berbagi',
  stopConfirm: 'Pemberi pinjaman tidak akan bisa melihat berkas Anda lagi. Berhenti berbagi?',
  stopYes: 'Ya, berhenti berbagi',
  stopNo: 'Tetap bagikan',
  stopping: 'Menghentikan…',

  activityTitle: 'Siapa yang sudah melihat berkas Anda',
  activityLead:
    'Setiap kali pemberi pinjaman membuka atau memutuskan berkas Anda, hal itu tampil di sini. Nama petugas dan catatan mereka tidak ditampilkan di sini.',
  activityEmpty: 'Belum ada yang terjadi pada berkas Anda.',
  activityFailed: 'Daftar ini belum bisa dimuat. Akan dicoba lagi saat halaman dimuat ulang.',
  activityTimes: (n: number) => `${n} kali`,
  activityEvents: {
    started: 'Anda memulai berkas ini',
    started_by_lender: 'Petugas kredit memulai berkas ini',
    invited: 'Pemberi pinjaman mengundang Anda mengirim catatan',
    invite_opened: 'Anda membuka undangan pemberi pinjaman',
    consent_given: 'Anda menyetujui pemeriksaan',
    consent_withdrawn: 'Anda menarik persetujuan',
    checked: 'Catatan Anda sudah diperiksa',
    checked_again: 'Berkas Anda diperiksa ulang dengan jawaban Anda',
    shared: 'Anda membuat tautan berbagi',
    opened_by_lender: 'Pemberi pinjaman membuka berkas Anda',
    share_stopped: 'Anda berhenti berbagi; pemberi pinjaman tidak bisa lagi membuka berkas Anda',
    decision_recommended: 'Petugas kredit mengusulkan keputusan',
    signoff_opened: 'Orang kedua di pemberi pinjaman mulai memeriksa keputusan',
    decision_reconsidered: 'Pemberi pinjaman meninjau ulang keputusan',
    signed_off: 'Orang kedua di pemberi pinjaman mengesahkan keputusan',
    sent_to_you: 'Keputusan pemberi pinjaman dikirim kepada Anda',
    offer_accepted: 'Anda menerima tawaran',
    offer_declined: 'Anda menolak tawaran',
    condition_met: 'Satu syarat ditandai sudah dipenuhi',
    records_sent: 'Anda mengirim catatan yang diminta',
  },
  shareNeedsCheck: 'Periksa catatan Anda dulu, lalu berkas bisa dibagikan.',

  waitingTitle: 'Pemberi pinjaman sedang memutuskan',
  waitingText:
    'Petugas kredit sudah memberi rekomendasi, dan orang kedua di pemberi pinjaman sedang memeriksanya. Keputusannya akan muncul di sini.',
  decisionTitle: {
    approve: 'Tawaran pinjaman Anda',
    decline: 'Keputusan pemberi pinjaman',
    request_more: 'Pemberi pinjaman meminta catatan tambahan',
  },
  letterFrom: 'Dari pemberi pinjaman Anda',
  letterNote: 'Angka-angka dihitung dari tawaran, bukan ditulis oleh AI.',
  offerAmount: 'Pinjaman',
  offerInstalment: 'Per bulan',
  offerMonths: 'Selama',
  monthsValue: (n: number) => `${n} bulan`,
  offerRate: 'Bunga per tahun',
  offerTotal: 'Total yang Anda bayar',
  schedule: {
    summary: 'Lihat setiap bulan',
    caption: 'Yang Anda bayar setiap bulan, bunga di dalamnya, dan sisa pinjaman setelahnya.',
    month: 'Bulan',
    instalment: 'Cicilan',
    interest: 'Bunga',
    principal: 'Pokok',
    balance: 'Sisa pinjaman',
  },
  acceptOffer: 'Terima tawaran',
  declineOffer: 'Tolak tawaran',
  declineConfirm:
    'Tolak tawaran ini? Pemberi pinjaman akan diberi tahu. Berkas ini tetap milik Anda.',
  declineYes: 'Ya, tolak',
  declineNo: 'Kembali',
  answering: 'Mengirim…',
  offerAccepted:
    'Anda menerima tawaran ini. Pemberi pinjaman akan menghubungi Anda untuk langkah berikutnya.',
  offerDeclined: 'Anda menolak tawaran ini. Pemberi pinjaman sudah diberi tahu.',
  conditionsTitle: 'Sebelum dana dicairkan',
  conditionsLead:
    'Pemberi pinjaman meminta hal-hal ini. Jika perlu catatan, kirim di Catatan Anda di bawah, lalu ketuk Selesai.',
  conditionsAfterAccept: 'Terima tawaran dulu, lalu centang satu per satu.',
  conditionDone: 'Selesai',
  conditionMet: 'Selesai',
  conditionNeeds: (kind: string) => `Ini perlu catatan baru (${kind}). Kirim dulu di Catatan Anda.`,
  allConditionsMet: 'Semua yang diminta pemberi pinjaman sudah selesai.',
  requestedTitle: 'Yang diminta pemberi pinjaman',
  requestedLead:
    'Belum ada keputusan. Tambahkan catatan ini di Catatan Anda di bawah, lalu beri tahu pemberi pinjaman.',
  sendToLender: 'Kirim ke pemberi pinjaman',
  sendNeedsRecords: 'Tambahkan setidaknya satu catatan baru di bawah dulu.',
  sentToLender: (n: number) =>
    `Terkirim. Pemberi pinjaman tahu Anda menambah ${n} catatan baru.`,
  checkLocked:
    'Pemberi pinjaman sedang memutuskan berdasarkan berkas saat ini, jadi berkas tidak bisa diperiksa ulang. Anda tetap bisa mengirim catatan yang diminta.',

  remindButton: 'Ingatkan saya untuk memeriksa lagi',
  remindLead:
    'Kumpulkan catatan beberapa minggu lagi, lalu periksa ulang. Tambahkan pengingat di Google Calendar untuk 30 hari lagi, berisi saran-saran ini.',
  remindLeadDeclined:
    'Keputusan ini tentang berkas Anda saat ini. Dengan catatan beberapa minggu lagi, berkas Anda bisa lebih kuat: tambahkan pengingat di Google Calendar untuk 30 hari lagi, berisi saran dari ringkasan Anda.',
  remindEventTitle: 'Periksa lagi berkas LedgerLens saya',
  remindDetails: (tips: string[], url: string) =>
    [
      'Saatnya melihat lagi berkas LedgerLens Anda: tambahkan catatan yang terkumpul sejak pemeriksaan terakhir, lalu periksa ulang.',
      '',
      ...(tips.length ? ['Saran dari pemeriksaan terakhir:', ...tips.map((tip) => `• ${tip}`), ''] : []),
      `Berkas Anda (buka di peramban yang sama seperti sebelumnya): ${url}`,
    ].join('\n'),
  opensCalendar: ' (membuka Google Calendar di tab baru)',

  deleteTitle: 'Hapus berkas saya',
  deleteLead:
    'Anda boleh menghapus berkas ini beserta seluruh isinya kapan saja: foto, rekaman, jawaban, ringkasan dan tautan berbagi. Undang-Undang Pelindungan Data Pribadi (UU PDP) menjamin hak Anda ini.',
  deleteButton: 'Hapus berkas saya',
  deleteConfirm:
    'Hapus berkas ini untuk selamanya? Semua foto, rekaman dan jawaban dihapus, dan pemberi pinjaman yang Anda beri akses juga kehilangan berkas ini. Ini tidak bisa dibatalkan.',
  deleteYes: 'Ya, hapus semuanya',
  deleteNo: 'Simpan berkas saya',
  deleting: 'Menghapus…',
  deleteBlockedDeciding:
    'Pemberi pinjaman sedang memutuskan berkas ini, jadi berkas belum bisa dihapus. Anda bisa menghapusnya setelah ada keputusan.',
  deleteBlockedAccepted:
    'Anda sudah menerima tawaran pinjaman untuk berkas ini, jadi pemberi pinjaman perlu menyimpannya selama pinjaman diurus. Tanyakan kepada pemberi pinjaman jika Anda ingin berkas ini dihapus.',
  deleteBlockedChecking: 'Catatan Anda sedang diperiksa. Tunggu sampai selesai, lalu berkas bisa dihapus.',

  status: {
    draft: 'Menunggu persetujuan Anda',
    collecting: 'Mengirim catatan',
    analyzing: 'Sedang diperiksa',
    needs_follow_up: 'Ada pertanyaan untuk Anda',
    ready: 'Sudah diperiksa',
    in_review: 'Ditinjau pemberi pinjaman',
    awaiting_signoff: 'Pemberi pinjaman sedang memutuskan',
    decided: 'Pemberi pinjaman sudah memutuskan',
  },
}

const STRINGS: Record<Lang, OwnerStrings> = { en: EN, id: ID }

/** The owner's chosen language, its strings, and a way to change it. */
export function useLang() {
  const lang = useSyncExternalStore(subscribe, () => current, () => 'en' as Lang)
  return { lang, t: STRINGS[lang], setLang, toggle: () => setLang(lang === 'en' ? 'id' : 'en') }
}
