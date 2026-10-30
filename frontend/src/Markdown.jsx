// A small, safe Markdown renderer for Ask Visor answers: paragraphs, bullet lists, tables, **bold**
// and `code`. Builds React elements only — never injects HTML — so model output can't run script.
function inline(text, keyBase) {
  const out = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g
  let last = 0
  let m
  let i = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const t = m[0]
    out.push(t.startsWith('**')
      ? <strong key={`${keyBase}-${i++}`}>{t.slice(2, -2)}</strong>
      : <code key={`${keyBase}-${i++}`}>{t.slice(1, -1)}</code>)
    last = m.index + t.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

const cells = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())

export default function Markdown({ text }) {
  const lines = (text || '').split('\n')
  const blocks = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1])) {
      const head = cells(line)
      const rows = []
      i += 2
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(cells(lines[i++]))
      blocks.push(
        <div className="mdtable" key={`t${i}`}>
          <table>
            <thead><tr>{head.map((h, k) => <th key={k}>{inline(h, `h${i}${k}`)}</th>)}</tr></thead>
            <tbody>{rows.map((r, ri) => <tr key={ri}>{r.map((c, k) => <td key={k}>{inline(c, `c${i}${ri}${k}`)}</td>)}</tr>)}</tbody>
          </table>
        </div>,
      )
      continue
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*]\s+/, ''))
      blocks.push(<ul key={`u${i}`}>{items.map((t, k) => <li key={k}>{inline(t, `l${i}${k}`)}</li>)}</ul>)
      continue
    }
    if (/^#{1,4}\s+/.test(line)) {
      blocks.push(<p key={`h${i}`}><strong>{inline(line.replace(/^#{1,4}\s+/, ''), `hh${i}`)}</strong></p>)
      i++
      continue
    }
    if (!line.trim()) { i++; continue }
    const para = []
    while (i < lines.length && lines[i].trim() && !/^\s*(\||[-*]\s|#{1,4}\s)/.test(lines[i])) para.push(lines[i++])
    blocks.push(<p key={`p${i}`}>{inline(para.join(' '), `p${i}`)}</p>)
  }
  return <div className="md">{blocks}</div>
}
