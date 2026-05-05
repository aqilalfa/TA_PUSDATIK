import { describe, it, expect } from 'vitest'
import {
  stripReferenceBlock,
  injectCitationSpans,
  renderLatex,
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

    expect(result).toContain('<span class="citation">1</span>')
    expect(result).toContain('<span class="citation">2</span>')
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
})
