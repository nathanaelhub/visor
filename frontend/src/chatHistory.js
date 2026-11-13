// Saved conversations (spec 09): turn the server's saved messages back into the chat's own shape.
// Saved tool calls keep the input and one-line summary only; the full results aren't stored.
export function fromSaved(messages) {
  return messages.map((m) => (m.role === 'user'
    ? { role: 'user', text: m.text }
    : { role: 'bot', answer: m.text, model: m.model, sources: [], saved: true,
        tool_calls: (m.tools || []).map((t) => ({ ...t, result: null, source: null })) }))
}

/** The line under the chat box: what happens to this conversation. */
export function savedNotice(account) {
  return account ? 'Saved for one year. Your advisor and Visor admins can read it.' : 'Not saved.'
}
