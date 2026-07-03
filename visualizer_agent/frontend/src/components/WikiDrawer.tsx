import { useEffect, useState } from "react";
import { api } from "../api/hooks";
import { Badge } from "./ui/ui";
import type { GraphNode } from "../api/types";
import "./wikidrawer.css";

// Minimal, safe Markdown → HTML for the wiki body (headings, bold, italics,
// [[wikilinks]], bullets). The wiki is trusted first-party content.
function renderMarkdown(md: string): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = md.replace(/^---[\s\S]*?---/, "").trim().split("\n"); // strip frontmatter
  const out: string[] = [];
  let inList = false;
  for (let raw of lines) {
    const line = esc(raw);
    if (/^\s*[-*]\s+/.test(raw)) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`);
      continue;
    }
    if (inList) { out.push("</ul>"); inList = false; }
    if (/^###\s/.test(raw)) out.push(`<h4>${inline(line.replace(/^###\s/, ""))}</h4>`);
    else if (/^##\s/.test(raw)) out.push(`<h3>${inline(line.replace(/^##\s/, ""))}</h3>`);
    else if (/^#\s/.test(raw)) out.push(`<h2>${inline(line.replace(/^#\s/, ""))}</h2>`);
    else if (raw.trim() === "") out.push("");
    else out.push(`<p>${inline(line)}</p>`);
  }
  if (inList) out.push("</ul>");
  return out.join("\n");

  function inline(s: string): string {
    return s
      .replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink">$1</span>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }
}

export default function WikiDrawer({ node, onClose }: { node: GraphNode | null; onClose: () => void }) {
  const [content, setContent] = useState<string>("");
  const [live, setLive] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!node) return;
    setLoading(true);
    setContent("");
    api.wiki(node.name).then((env) => {
      setContent(env.data.content || "_No wiki page found for this entity._");
      setLive(env.live);
      setLoading(false);
    });
  }, [node]);

  return (
    <>
      <div className={`wd-scrim${node ? " open" : ""}`} onClick={onClose} />
      <aside className={`wd${node ? " open" : ""}`} aria-hidden={!node}>
        {node && (
          <>
            <div className="wd-head">
              <div>
                <div className="wd-type label-sm">{node.type}</div>
                <h2 className="wd-title">{node.name}</h2>
              </div>
              <button className="wd-close press" onClick={onClose} aria-label="Close">
                ✕
              </button>
            </div>
            <div className="wd-meta">
              <Badge tone={bandTone(node.band)}>{node.band}</Badge>
              <span className="wd-meta-item mono">risk {(node.score * 100).toFixed(0)}%</span>
              <span className="wd-meta-item mono">{node.degree} links</span>
              {!live && <span className="wd-offline mono">offline</span>}
            </div>
            <div className="wd-body">
              {loading ? (
                <div className="wd-skeleton">
                  <span className="skeleton wd-sk-line" />
                  <span className="skeleton wd-sk-line" />
                  <span className="skeleton wd-sk-line short" />
                </div>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }} />
              )}
            </div>
            <div className="wd-foot label-sm">Retrieved from SAGE knowledge base · not generated</div>
          </>
        )}
      </aside>
    </>
  );
}

function bandTone(band: string): "green" | "amber" | "coral" | "red" | "cyan" {
  return band === "CRITICAL" ? "red" : band === "ACTION" ? "coral" : band === "ELEVATED" ? "amber" : band === "WATCH" ? "amber" : "green";
}
