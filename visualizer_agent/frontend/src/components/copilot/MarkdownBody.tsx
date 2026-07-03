import type { ReactNode } from "react";
import type { CopilotSource } from "../../api/types";

// Lightweight Markdown → React renderer tuned for the SAGE copilot: headings,
// numbered lists (with number chips), bullet lists, tables, bold, and inline
// [n] citation chips that resolve to the numbered sources (Perplexity-style).
export function MarkdownBody({
  text,
  sources,
  onCite,
}: {
  text: string;
  sources: CopilotSource[];
  onCite?: (source: CopilotSource) => void;
}) {
  const lines = text.split("\n");
  const out: ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Heading (## / ###)
    const h = line.match(/^(#{1,3})\s+(.*)/);
    if (h) {
      const lvl = h[1].length;
      out.push(
        <div key={i} className={`md-h md-h${lvl}`}>
          {inline(h[2], sources, onCite)}
        </div>
      );
      i++;
      continue;
    }

    // Table
    if (/^\s*\|.+\|/.test(line)) {
      const rows: string[][] = [];
      while (i < lines.length && /^\s*\|.+\|/.test(lines[i])) {
        const cells = lines[i].split("|").slice(1, -1).map((c) => c.trim());
        if (!cells.every((c) => /^[-:\s]*$/.test(c))) rows.push(cells);
        i++;
      }
      if (rows.length) {
        const [head, ...body] = rows;
        out.push(
          <div key={`t${i}`} className="md-table-wrap">
            <table className="md-table">
              <thead>
                <tr>{head.map((c, k) => <th key={k}>{inline(c, sources, onCite)}</th>)}</tr>
              </thead>
              <tbody>
                {body.map((r, ri) => (
                  <tr key={ri}>{r.map((c, k) => <td key={k}>{inline(c, sources, onCite)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      continue;
    }

    // Numbered list
    if (/^\s*\d+\.\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      out.push(
        <ol key={`ol${i}`} className="md-ol">
          {items.map((it, j) => (
            <li key={j}>
              <span className="md-num">{j + 1}</span>
              <span className="md-li-body">{inline(it, sources, onCite)}</span>
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // Bullet list (supports nested indent by trimming)
    if (/^\s*[-•*]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-•*]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-•*]\s+/, ""));
        i++;
      }
      out.push(
        <ul key={`ul${i}`} className="md-ul">
          {items.map((it, j) => (
            <li key={j}>
              <span className="md-dot" />
              <span className="md-li-body">{inline(it, sources, onCite)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    if (!line.trim()) {
      out.push(<div key={`sp${i}`} className="md-gap" />);
      i++;
      continue;
    }

    out.push(
      <p key={i} className="md-p">
        {inline(line, sources, onCite)}
      </p>
    );
    i++;
  }

  return <div className="md-body">{out}</div>;
}

// Inline: **bold**, `code`, [n] citation chips.
function inline(
  text: string,
  sources: CopilotSource[],
  onCite?: (s: CopilotSource) => void
): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(\*\*(.+?)\*\*)|(`([^`]+)`)|(\[(\d+)\])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1]) {
      parts.push(<strong key={key++}>{m[2]}</strong>);
    } else if (m[3]) {
      parts.push(<code key={key++} className="md-code">{m[4]}</code>);
    } else if (m[5]) {
      const n = Number(m[6]);
      const src = sources.find((s) => s.index === n);
      parts.push(
        <button
          key={key++}
          type="button"
          className="cite-mark"
          title={src ? `${src.entity} (${src.type})` : `Source ${n}`}
          onClick={() => src && onCite?.(src)}
        >
          {n}
        </button>
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length ? parts : [text];
}
