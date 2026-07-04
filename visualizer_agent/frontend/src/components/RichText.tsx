import type { ReactNode } from "react";
import "./richtext.css";

/**
 * Renders a single narrative paragraph (wiki "Current Assessment", procurement
 * rationale, SPR policy memo, …) with **bold**, *italic*, `code`, and
 * [[wikilinks]] — instead of showing the raw markdown/wikilink syntax verbatim.
 * [[wikilinks]] are optionally clickable (onWikilink) to open that entity's
 * wiki page, matching how wikilinks behave inside the drawer itself.
 */
export function RichText({
  text,
  onWikilink,
  className = "",
}: {
  text: string;
  onWikilink?: (entity: string) => void;
  className?: string;
}) {
  return <span className={`rich-text ${className}`}>{inline(text, onWikilink)}</span>;
}

function inline(text: string, onWikilink?: (entity: string) => void): ReactNode[] {
  const parts: ReactNode[] = [];
  // Order matters: wikilinks first (contain no ** or `), then bold, then italic, then code.
  const re = /(\[\[([^\]]+)\]\])|(\*\*(.+?)\*\*)|(`([^`]+)`)|(\*([^*]+)\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1]) {
      const entity = m[2];
      parts.push(
        onWikilink ? (
          <button
            key={key++}
            type="button"
            className="rich-wikilink"
            onClick={(e) => {
              // Narrative text often sits inside a clickable card (e.g. a
              // recommendation card that navigates on click) — stop the click
              // from also triggering the ancestor's handler.
              e.stopPropagation();
              onWikilink(entity);
            }}
          >
            {entity}
          </button>
        ) : (
          <span key={key++} className="rich-wikilink rich-wikilink-static">
            {entity}
          </span>
        )
      );
    } else if (m[3]) {
      parts.push(<strong key={key++}>{m[4]}</strong>);
    } else if (m[5]) {
      parts.push(
        <code key={key++} className="rich-code">
          {m[6]}
        </code>
      );
    } else if (m[7]) {
      parts.push(<em key={key++}>{m[8]}</em>);
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length ? parts : [text];
}
