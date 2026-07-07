import katex from 'katex'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

/**
 * Strip the "Referensi Dokumen:" block appended by the backend.
 * The block is redundant because the frontend renders SourceCard components.
 */
export function stripReferenceBlock(text) {
  if (!text) return ''
  // Backend appends "\n\nReferensi Dokumen:\n[N] Title ..." via append_citation_reference_block
  const parts = text.split(/\n+Referensi\s+Dokumen\s*:\s*\n/i)
  return parts[0].trim()
}

/**
 * Replace [N] tokens in rendered HTML with interactive citation button elements.
 * Must be called AFTER marked.parse() so we only target text nodes, not code.
 * Produces <button> instead of <span> to allow click event delegation in MessageBubble.
 */
export function injectCitationSpans(html) {
  return html.replace(
    /\[(\d+)\]/g,
    '<button class="citation" data-citation-id="$1" type="button">$1</button>'
  )
}

/**
 * Render LaTeX display ($$...$$) and inline ($...$) math using KaTeX.
 * Must be called BEFORE marked.parse() to protect formulas from markdown.
 */
export function renderLatex(text) {
  if (!text) return ''

  // Display math $$...$$ — process first (greedy match before inline)
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: true,
        throwOnError: false,
        output: 'html',
      })
    } catch {
      return `$$${formula}$$`
    }
  })

  // Inline math $...$ — single-line only (avoid greedy cross-paragraph matches)
  result = result.replace(/\$([^\$\n]+?)\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: false,
        throwOnError: false,
        output: 'html',
      })
    } catch {
      return `$${formula}$`
    }
  })

  return result
}

const SECTION_LABELS = 'jawaban\\s+ringkas|poin\\s+penting|poin\\s+kewajiban|dokumen\\s+yang\\s+perlu\\s+disiapkan|rujukan|referensi|dasar\\s+hukum|catatan|kesimpulan|rekomendasi|analisis'
const SECTION_HEADING_PATTERN = new RegExp(`^(${SECTION_LABELS})(\\s*:)?$`, 'i')
const SECTION_PREFIX_PATTERN = new RegExp(`^(${SECTION_LABELS})\\s*:\\s+(.+)$`, 'i')
const MAX_INLINE_HIGHLIGHTS = 4
const HIGHLIGHT_OPEN = '<mark class="answer-highlight">'
const HIGHLIGHT_CLOSE = '</mark>'

const INLINE_HIGHLIGHT_RULES = [
  // Rujukan regulasi formal: diprioritaskan agar "adalah Perpres ..." tidak dianggap definisi umum.
  /\b((?:Peraturan\s+(?:Presiden|Menteri)|Perpres|Permen(?:\s+PANRB)?|Perka\s+[A-ZÀ-ÿ]+|Keputusan\s+[A-ZÀ-ÿ]+)[^.,;\n]{0,90}?(?:Nomor|No\.)\s+[^.,;\n]{1,80}?\s+Tahun\s+\d{4})\b/i,

  // Definisi inti: "SPBE adalah ... untuk ..."
  /(\b(?:adalah|merupakan|dimaksud\s+dengan|didefinisikan\s+sebagai)\s+)([^.?!\n]{24,180}?)(?=(?:\s+untuk\b|\s+yang\s+diatur\b|\s+yang\s+digunakan\b|\s+sesuai\b|\s+sebagaimana\b|\s+\[\d+\]|[.,;]|$))/i,

  // Status keterbatasan sumber: penting agar pengguna tahu batas kepastian jawaban.
  /((?:tidak\s+ada\s+peraturan|tidak\s+secara\s+spesifik|belum\s+tersedia|rujukan\s+belum\s+tersedia|dokumen\s+tidak\s+menyebutkan\s+secara\s+eksplisit|tidak\s+dapat|tidak\s+boleh|dilarang)[^.;\n]{0,150})/i,

  // Kewajiban/keharusan hukum.
  /((?:[A-Za-zÀ-ÿ0-9][^.;\n]{0,120}?\b(?:wajib|harus|perlu|diwajibkan|bertanggung\s+jawab)\b[^.;\n]{8,150}?)(?=(?:\s+\[\d+\]|[.;]|$)))/i,

  // Pasal/ayat dan struktur angka penting.
  /\b((?:Pasal\s+\d+[A-Za-z]*(?:\s+Ayat\s+\(\d+\))?|Ayat\s+\(\d+\)|\d+\s+(?:domain|indikator|level|tingkat|aspek)))\b/i,

  // Kesimpulan berbasis sumber.
  /((?:berdasarkan\s+dokumen\s+yang\s+tersedia|dapat\s+disimpulkan|berdasarkan\s+sumber\s+yang\s+tersedia)[^.;\n]{0,140})/i,

  // Istilah/topik penting yang ditulis dalam tanda kutip.
  /"([^"\n]{16,160})"/,
]

function stripMarkdownLabelMarkers(value) {
  return value
    .replace(/\*\*/g, '')
    .replace(/__/g, '')
    .trim()
}

/**
 * Convert common plain-text legal answer section labels into markdown headings.
 * This preserves the words produced by the chatbot while allowing the UI to
 * style structured answers without changing backend prompts or RAG logic.
 */
export function normalizeLegalAnswerSections(text) {
  if (!text) return ''

  return text
    .split('\n')
    .map((line) => {
      const trimmed = line.trim()
      if (!trimmed) return line
      if (/^(#{1,6}|[-*+]\s|\d+[.)]\s)/.test(trimmed)) return line
      const indent = line.match(/^\s*/)?.[0] || ''
      const normalizedLabel = stripMarkdownLabelMarkers(trimmed)

      const prefixMatch = normalizedLabel.match(SECTION_PREFIX_PATTERN)
      if (prefixMatch) {
        return `${indent}### ${prefixMatch[1]}\n${indent}${prefixMatch[2]}`
      }

      if (!SECTION_HEADING_PATTERN.test(normalizedLabel)) return line

      return `${indent}### ${normalizedLabel.replace(/\s*:$/, '')}`
    })
    .join('\n')
}

function shouldSkipInlineHighlight(line) {
  const trimmed = line.trim()
  return !trimmed || /^(#{1,6}|```)/.test(trimmed) || trimmed.includes('answer-highlight')
}

function highlightMatch(match, ...groups) {
  // Definition rule captures a prefix ("adalah", "merupakan") and phrase.
  if (/^(adalah|merupakan|dimaksud\s+dengan|didefinisikan\s+sebagai)\s+/i.test(groups[0] || '')) {
    const [prefix, phrase] = groups
    return `${prefix}${HIGHLIGHT_OPEN}${phrase.trim()}${HIGHLIGHT_CLOSE}`
  }

  // Quoted phrase rule captures only the inside of quotes.
  if (match.startsWith('"') && match.endsWith('"')) {
    const [phrase] = groups
    return `"${HIGHLIGHT_OPEN}${phrase.trim()}${HIGHLIGHT_CLOSE}"`
  }

  const [phrase] = groups
  return `${HIGHLIGHT_OPEN}${String(phrase || match).trim()}${HIGHLIGHT_CLOSE}`
}

/**
 * Add lightweight visual emphasis to important phrases inside answer paragraphs.
 * This does not alter chatbot wording; it only wraps selected phrases with a
 * sanitized <mark> tag so the UI can improve scanning/readability.
 */
export function highlightImportantAnswerPhrases(text) {
  if (!text) return ''

  let insideCodeBlock = false
  let highlightCount = 0

  return text
    .split('\n')
    .map((line) => {
      if (line.trim().startsWith('```')) {
        insideCodeBlock = !insideCodeBlock
        return line
      }
      if (insideCodeBlock || shouldSkipInlineHighlight(line)) return line

      for (const rule of INLINE_HIGHLIGHT_RULES) {
        if (highlightCount >= MAX_INLINE_HIGHLIGHTS) return line
        if (!rule.test(line)) continue

        rule.lastIndex = 0
        const highlighted = line.replace(rule, (...args) => {
          const [match, ...rest] = args
          const groups = rest.slice(0, -2)
          return highlightMatch(match, ...groups)
        })
        if (highlighted !== line) {
          highlightCount += 1
          return highlighted
        }
      }

      return line
    })
    .join('\n')
}

/**
 * Full pipeline: strip reference block → render LaTeX → render markdown
 * → sanitize HTML → inject citation spans.
 */
export function formatMessageContent(text) {
  if (!text) return ''

  const stripped = stripReferenceBlock(text)
  if (!stripped) return ''

  const normalized = normalizeLegalAnswerSections(stripped)
  const highlighted = highlightImportantAnswerPhrases(normalized)
  const withLatex = renderLatex(highlighted)

  const html = marked.parse(withLatex)

  const safe = DOMPurify.sanitize(html, {
    // Allow KaTeX-generated classes and inline styles
    FORCE_BODY: true,
    ADD_TAGS: ['mark'],
    ADD_ATTR: ['class', 'style', 'aria-hidden'],
  })

  return injectCitationSpans(safe)
}
