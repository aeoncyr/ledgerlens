// Words for the business owner's pages, in English (the default) and Bahasa Indonesia. The choice
// is remembered in this browser and shared by every owner page through a tiny store.
import { useSyncExternalStore } from 'react'

export type Lang = 'en' | 'id'

const STORAGE_KEY = 'ledgerlens-owner-lang'

function readStored(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'id' ? 'id' : 'en'
  } catch {
    return 'en'
  }
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
  tagline: 'for business owners',
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
  consentButton: 'I agree, let’s start',
  consentNotNow: 'Not now',
  consentSaving: 'Saving…',

  // Evidence
  sendTitle: 'Send photos of your records',
  moreTitle: 'Your records',
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
  checkFailed: 'The check stopped before it finished.',

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
  recheckButton: 'Check again with my answers',
  recheckNeedsAnswer: 'Write at least one answer first.',
  savingAnswers: 'Saving your answers…',

  // Share
  shareTitle: 'Share with a lender',
  shareLead:
    'Send this link to the loan officer at your bank, koperasi or BPR. They see your records and what was checked. You can stop sharing at any time.',
  shareButton: 'Create my share link',
  sharing: 'Creating…',
  shareLinkLabel: 'Your share link',
  shareCodeLabel: 'Or read out this code',
  copy: 'Copy link',
  copied: 'Copied',
  whatsapp: 'Send on WhatsApp',
  whatsappText: (url: string, code: string) =>
    `Hello, here is the credit file for my business on LedgerLens. It shows my records and what was checked. Open: ${url} (code ${code})`,
  stopSharing: 'Stop sharing',
  stopConfirm: 'The lender will lose access to your file. Stop sharing?',
  stopYes: 'Yes, stop sharing',
  stopNo: 'Keep sharing',
  stopping: 'Stopping…',
  shareNeedsCheck: 'Check your records first, then you can share the file.',

  status: {
    draft: 'Needs your agreement',
    collecting: 'Sending records',
    analyzing: 'Being checked',
    needs_follow_up: 'Questions for you',
    ready: 'Checked',
    in_review: 'With the lender',
    decided: 'The lender has decided',
  } as Record<string, string>,
}

export type OwnerStrings = typeof EN

const ID: OwnerStrings = {
  langName: 'Bahasa Indonesia',
  switchTo: 'English',
  switchLabel: 'Read in English',
  tagline: 'untuk pemilik usaha',
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
  consentButton: 'Saya setuju, mulai',
  consentNotNow: 'Nanti saja',
  consentSaving: 'Menyimpan…',

  sendTitle: 'Kirim foto catatan Anda',
  moreTitle: 'Catatan Anda',
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
  checkFailed: 'Pemeriksaan berhenti sebelum selesai.',

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
  recheckButton: 'Periksa ulang dengan jawaban saya',
  recheckNeedsAnswer: 'Tulis setidaknya satu jawaban dulu.',
  savingAnswers: 'Menyimpan jawaban Anda…',

  shareTitle: 'Bagikan ke pemberi pinjaman',
  shareLead:
    'Kirim tautan ini ke petugas kredit di bank, koperasi atau BPR Anda. Mereka melihat catatan Anda dan hasil pemeriksaannya. Anda bisa berhenti berbagi kapan saja.',
  shareButton: 'Buat tautan berbagi',
  sharing: 'Membuat…',
  shareLinkLabel: 'Tautan berbagi Anda',
  shareCodeLabel: 'Atau bacakan kode ini',
  copy: 'Salin tautan',
  copied: 'Tersalin',
  whatsapp: 'Kirim lewat WhatsApp',
  whatsappText: (url: string, code: string) =>
    `Halo, ini berkas kredit usaha saya di LedgerLens. Isinya catatan saya dan hasil pemeriksaannya. Buka: ${url} (kode ${code})`,
  stopSharing: 'Berhenti berbagi',
  stopConfirm: 'Pemberi pinjaman tidak akan bisa melihat berkas Anda lagi. Berhenti berbagi?',
  stopYes: 'Ya, berhenti berbagi',
  stopNo: 'Tetap bagikan',
  stopping: 'Menghentikan…',
  shareNeedsCheck: 'Periksa catatan Anda dulu, lalu berkas bisa dibagikan.',

  status: {
    draft: 'Menunggu persetujuan Anda',
    collecting: 'Mengirim catatan',
    analyzing: 'Sedang diperiksa',
    needs_follow_up: 'Ada pertanyaan untuk Anda',
    ready: 'Sudah diperiksa',
    in_review: 'Ditinjau pemberi pinjaman',
    decided: 'Pemberi pinjaman sudah memutuskan',
  },
}

const STRINGS: Record<Lang, OwnerStrings> = { en: EN, id: ID }

/** The owner's chosen language, its strings, and a way to change it. */
export function useLang() {
  const lang = useSyncExternalStore(subscribe, () => current, () => 'en' as Lang)
  return { lang, t: STRINGS[lang], setLang, toggle: () => setLang(lang === 'en' ? 'id' : 'en') }
}
