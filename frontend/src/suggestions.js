// Ask Visor's suggested questions (R3-F3). Students get two general questions and two about their own
// major, naming real courses from that program; staff questions don't depend on the major.

const GENERAL = ['Which requirements am I still missing?', 'What should I register for next term, and why?']

const BY_PROGRAM = {
  'cs-bs-2026-27': ['What happens if I fail Data Structures?', 'Can you move Operating Systems to next fall?'],
  'bio-bs-2026-27': ['What happens if I fail Principles of Biology: Cell and Genetics?',
    'Can I take Organic Chemistry I in the summer?'],
  'psych-bs-2026-27': ['When should I take Behavioral Statistics?',
    'What happens if I fail Introduction to Psychology?'],
  'nursing-bsn-2026-27': ['When do I need admission to the nursing program?',
    'What happens if I fail Health Assessment?'],
  'mgmt-bba-2026-27': ['What happens if I fail Financial Accounting?', 'Can I take Principles of Finance earlier?'],
}

const STAFF = {
  advisor: ['Why does this plan need review?', 'Which courses in this plan are offered only once a year?',
    'What does this student’s transfer credit count as?'],
  registrar: ['What does CISP 1020 at Nashville State count as?', 'Is CSCI 1020 at Columbia State confirmed?',
    'What are the prerequisites for CS 3633?'],
}

export function suggestionsFor(role, programId) {
  if (role !== 'student') return STAFF[role] ?? []
  return [...GENERAL, ...(BY_PROGRAM[programId] ?? [])]
}
