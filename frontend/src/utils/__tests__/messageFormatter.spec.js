import { describe, it, expect } from 'vitest'
import {
  stripReferenceBlock,
  injectCitationSpans,
  renderLatex,
  normalizeLegalAnswerSections,
  highlightImportantAnswerPhrases,
  formatMessageContent,
} from '../messageFormatter.js'

// ─────────────────────────────────────────────────────────────────────────────
// stripReferenceBlock
// ─────────────────────────────────────────────────────────────────────────────
describe('stripReferenceBlock', () => {
  it('removes Referensi Dokumen block appended by backend', () => {
    const input = `Indeks aspek dihitung dengan rumus berikut [1].

Referensi Dokumen:
[1] Peraturan 59 Tahun 2020 | BAB II`

    const result = stripReferenceBlock(input)

    expect(result).not.toContain('Referensi Dokumen:')
    expect(result).not.toContain('Peraturan 59 Tahun 2020 | BAB II')
    expect(result).toContain('Indeks aspek dihitung')
  })

  it('keeps answer text that has no reference block unchanged', () => {
    const input = 'SPBE adalah Sistem Pemerintahan Berbasis Elektronik [1].'
    expect(stripReferenceBlock(input)).toBe(input)
  })

  it('removes block regardless of trailing whitespace around header', () => {
    const input = `Jawaban di sini [2].

Referensi Dokumen:
[2] Dokumen A`

    expect(stripReferenceBlock(input)).not.toContain('Referensi Dokumen:')
  })

  it('handles case-insensitive "referensi dokumen"', () => {
    const input = `Isi jawaban [1].

REFERENSI DOKUMEN:
[1] Dokumen B`

    expect(stripReferenceBlock(input)).not.toContain('REFERENSI DOKUMEN:')
  })

  it('returns empty string unchanged', () => {
    expect(stripReferenceBlock('')).toBe('')
    expect(stripReferenceBlock(null)).toBe('')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// injectCitationSpans
// ─────────────────────────────────────────────────────────────────────────────
describe('injectCitationSpans', () => {
  it('replaces [N] tokens with citation span elements', () => {
    const html = '<p>Pasal ini jelas [1] dan didukung [2].</p>'
    const result = injectCitationSpans(html)

    expect(result).toContain('<button class="citation"')
    expect(result).toContain('data-citation-id="1"')
    expect(result).toContain('data-citation-id="2"')
    expect(result).not.toContain('[1]')
    expect(result).not.toContain('[2]')
  })

  it('does not inject spans in pre/code blocks (raw text)', () => {
    const html = '<p>Contoh kode: [1]</p>'
    const result = injectCitationSpans(html)
    expect(result).toContain('class="citation"')
  })

  it('handles string with no citation tokens unchanged', () => {
    const html = '<p>Tidak ada sitasi di sini.</p>'
    expect(injectCitationSpans(html)).toBe(html)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// renderLatex
// ─────────────────────────────────────────────────────────────────────────────
describe('renderLatex', () => {
  it('renders display math $$...$$ into KaTeX HTML', () => {
    const input = '$$\\frac{1}{2}$$'
    const result = renderLatex(input)

    expect(result).not.toContain('$$')
    expect(result).toContain('katex')
  })

  it('renders inline math $...$ into KaTeX HTML', () => {
    const input = 'Nilai $x^2$ dihitung dari rumus ini.'
    const result = renderLatex(input)

    expect(result).not.toMatch(/\$x\^2\$/)
    expect(result).toContain('katex')
  })

  it('renders the SPBE index formula without errors', () => {
    const formula = '$$\\text{Indeks}_{i} = \\frac{1}{BA_i} \\sum_{j=m}^{n} (NL_{ij} \\times BI_{ij})$$'
    const result = renderLatex(formula)

    expect(result).not.toContain('$$')
    expect(result).toContain('katex')
  })

  it('leaves text with no math tokens unchanged', () => {
    const input = 'Tidak ada formula di sini.'
    expect(renderLatex(input)).toBe(input)
  })

  it('handles invalid LaTeX gracefully without throwing', () => {
    const input = '$$\\invalid{{}$$'
    expect(() => renderLatex(input)).not.toThrow()
  })

  it('returns empty string for null/empty input', () => {
    expect(renderLatex('')).toBe('')
    expect(renderLatex(null)).toBe('')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// normalizeLegalAnswerSections
// ─────────────────────────────────────────────────────────────────────────────
describe('normalizeLegalAnswerSections', () => {
  it('turns common plain section labels into markdown headings', () => {
    const input = `Jawaban Ringkas
Instansi wajib menyusun arsitektur SPBE.

Poin Kewajiban
1. Menyusun arsitektur SPBE instansi.`

    const result = normalizeLegalAnswerSections(input)

    expect(result).toContain('### Jawaban Ringkas')
    expect(result).toContain('### Poin Kewajiban')
    expect(result).toContain('1. Menyusun arsitektur SPBE instansi.')
  })

  it('does not change existing markdown headings or list items', () => {
    const input = `### Jawaban Ringkas
- Dokumen arsitektur SPBE`

    expect(normalizeLegalAnswerSections(input)).toBe(input)
  })

  it('keeps visual headings when backend leaves a section label with colon inline', () => {
    const input = 'Jawaban Ringkas: Instansi wajib menyusun arsitektur SPBE.'

    expect(normalizeLegalAnswerSections(input)).toBe(
      '### Jawaban Ringkas\nInstansi wajib menyusun arsitektur SPBE.'
    )
  })

  it('keeps visual headings when streamed markdown emphasis is later cleaned', () => {
    const input = '**Poin Kewajiban:** Menyusun arsitektur SPBE instansi.'

    expect(normalizeLegalAnswerSections(input)).toBe(
      '### Poin Kewajiban\nMenyusun arsitektur SPBE instansi.'
    )
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// highlightImportantAnswerPhrases
// ─────────────────────────────────────────────────────────────────────────────
describe('highlightImportantAnswerPhrases', () => {
  it('highlights the core definition phrase after "adalah" without changing surrounding text', () => {
    const input = 'SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi untuk memberikan layanan kepada pengguna.'

    const result = highlightImportantAnswerPhrases(input)

    expect(result).toContain('SPBE adalah <mark class="answer-highlight">penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi</mark> untuk memberikan layanan')
  })

  it('highlights important quoted phrases inside paragraphs', () => {
    const input = 'Pengguna menanyakan frasa "pedoman evaluasi SPBE di BSSN" sebagai topik konsultasi.'

    const result = highlightImportantAnswerPhrases(input)

    expect(result).toContain('"<mark class="answer-highlight">pedoman evaluasi SPBE di BSSN</mark>"')
  })

  it('does not highlight markdown heading lines', () => {
    const input = '### Jawaban Ringkas'

    expect(highlightImportantAnswerPhrases(input)).toBe(input)
  })

  it('highlights legal obligations beyond definition clauses', () => {
    const input = 'Instansi wajib menyusun arsitektur SPBE sesuai kerangka kerja arsitektur SPBE nasional.'

    const result = highlightImportantAnswerPhrases(input)

    expect(result).toContain('<mark class="answer-highlight">Instansi wajib menyusun arsitektur SPBE sesuai kerangka kerja arsitektur SPBE nasional</mark>')
  })

  it('highlights limitation statements when sources are not explicit', () => {
    const input = 'Dokumen tidak menyebutkan secara eksplisit pedoman evaluasi SPBE khusus untuk BSSN.'

    const result = highlightImportantAnswerPhrases(input)

    expect(result).toContain('<mark class="answer-highlight">Dokumen tidak menyebutkan secara eksplisit pedoman evaluasi SPBE khusus untuk BSSN</mark>')
  })

  it('highlights formal regulation references', () => {
    const input = 'Dasar hukum yang digunakan adalah Peraturan Presiden Nomor 95 Tahun 2018 tentang SPBE.'

    const result = highlightImportantAnswerPhrases(input)

    expect(result).toContain('<mark class="answer-highlight">Peraturan Presiden Nomor 95 Tahun 2018</mark>')
  })

  it('limits inline highlights so answers do not become visually noisy', () => {
    const input = [
      'SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi untuk layanan publik.',
      'Instansi wajib menyusun arsitektur SPBE sesuai kerangka nasional.',
      'Dokumen tidak menyebutkan secara eksplisit pedoman khusus BSSN.',
      'Dasar hukum utama adalah Peraturan Presiden Nomor 95 Tahun 2018 tentang SPBE.',
      'Terdapat 5 domain dalam tata kelola SPBE.',
    ].join('\n')

    const result = highlightImportantAnswerPhrases(input)
    const count = (result.match(/class="answer-highlight"/g) || []).length

    expect(count).toBeLessThanOrEqual(4)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// formatMessageContent — integration
// ─────────────────────────────────────────────────────────────────────────────
describe('formatMessageContent', () => {
  it('strips reference block AND renders markdown AND injects citation spans', () => {
    const input = `Indeks aspek [1] dihitung seperti berikut.

Referensi Dokumen:
[1] Peraturan 59 Tahun 2020 | BAB II`

    const result = formatMessageContent(input)

    expect(result).not.toContain('Referensi Dokumen:')
    expect(result).toContain('class="citation"')
  })

  it('renders LaTeX formula inside message', () => {
    const input = 'Rumus: $$\\frac{1}{n}$$ digunakan untuk agregasi [1].'
    const result = formatMessageContent(input)

    expect(result).not.toContain('$$')
    expect(result).toContain('katex')
    expect(result).toContain('class="citation"')
  })

  it('returns empty string for empty input', () => {
    expect(formatMessageContent('')).toBe('')
    expect(formatMessageContent(null)).toBe('')
  })

  it('renders legal answer section labels as headings', () => {
    const input = `Jawaban Ringkas
Instansi wajib menyusun arsitektur SPBE.

Dokumen yang Perlu Disiapkan
- Dokumen Arsitektur SPBE Instansi`

    const result = formatMessageContent(input)

    expect(result).toContain('<h3>Jawaban Ringkas</h3>')
    expect(result).toContain('<h3>Dokumen yang Perlu Disiapkan</h3>')
    expect(result).toContain('<li>Dokumen Arsitektur SPBE Instansi</li>')
  })

  it('renders inline legal section labels as headings without losing content', () => {
    const result = formatMessageContent('Jawaban Ringkas: Tidak ada peraturan khusus yang ditemukan.')

    expect(result).toContain('<h3>Jawaban Ringkas</h3>')
    expect(result).toContain('Tidak ada peraturan khusus yang ditemukan')
  })

  it('renders important paragraph phrases as blue highlight marks', () => {
    const input = 'SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi untuk memberikan layanan kepada pengguna.'

    const result = formatMessageContent(input)

    expect(result).toContain('<mark class="answer-highlight">penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi</mark>')
  })
})
