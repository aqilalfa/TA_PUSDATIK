import { describe, it, expect } from 'vitest'
import { validateFile } from '../validateUploadFile'

const MB = 1024 * 1024

function makeFile(name, sizeBytes, type = 'application/pdf') {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

describe('validateFile', () => {
  it('returns no errors or warnings for a valid small PDF', () => {
    const result = validateFile(makeFile('Perpres_95.pdf', 2 * MB))
    expect(result.errors).toHaveLength(0)
    expect(result.warnings).toHaveLength(0)
  })

  it('returns error when file exceeds 50 MB', () => {
    const result = validateFile(makeFile('big.pdf', 60 * MB))
    expect(result.errors.some(e => e.includes('50 MB'))).toBe(true)
  })

  it('returns error for unsupported extension (.txt)', () => {
    const result = validateFile(makeFile('notes.txt', 1 * MB, 'text/plain'))
    expect(result.errors.some(e => e.includes('PDF, DOC, atau DOCX'))).toBe(true)
  })

  it('returns no extension error for .docx', () => {
    const result = validateFile(makeFile('Laporan.docx', 3 * MB, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
    expect(result.errors).toHaveLength(0)
  })

  it('returns warning (not error) for filename with special characters', () => {
    const result = validateFile(makeFile('Laporan (FINAL) 2024!.pdf', 1 * MB))
    expect(result.errors).toHaveLength(0)
    expect(result.warnings.some(w => w.includes('karakter tidak umum'))).toBe(true)
  })

  it('returns no warning for filename with only safe characters', () => {
    const result = validateFile(makeFile('Laporan_Audit_2024.pdf', 1 * MB))
    expect(result.warnings).toHaveLength(0)
  })

  it('suggests underscores in place of spaces in sanitised filename', () => {
    const result = validateFile(makeFile('Laporan Final 2024!.pdf', 1 * MB))
    expect(result.warnings[0]).toContain('Laporan_Final_2024.pdf')
  })

  it('allows a file of exactly 50 MB (boundary)', () => {
    const result = validateFile(makeFile('exact.pdf', 50 * MB))
    expect(result.errors.some(e => e.includes('50 MB'))).toBe(false)
  })
})
