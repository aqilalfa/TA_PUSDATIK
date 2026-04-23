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
 * Replace [N] tokens in rendered HTML with styled citation span elements.
 * Must be called AFTER marked.parse() so we only target text nodes, not code.
 */
export function injectCitationSpans(html) {
  return html.replace(/\[(\d+)\]/g, '<span class="citation">$1</span>')
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

/**
 * Full pipeline: strip reference block → render LaTeX → render markdown
 * → sanitize HTML → inject citation spans.
 */
export function formatMessageContent(text) {
  if (!text) return ''

  const stripped = stripReferenceBlock(text)
  if (!stripped) return ''

  const withLatex = renderLatex(stripped)

  const html = marked.parse(withLatex)

  const safe = DOMPurify.sanitize(html, {
    // Allow KaTeX-generated classes and inline styles
    FORCE_BODY: true,
    ADD_ATTR: ['class', 'style', 'aria-hidden'],
  })

  return injectCitationSpans(safe)
}
