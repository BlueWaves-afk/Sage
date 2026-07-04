import { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/hooks";
import { Badge } from "./ui/ui";
import type { GraphNode } from "../api/types";
import "./wikidrawer.css";

// ── Markdown renderer ────────────────────────────────────────────────────────
function renderMarkdown(md: string): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = md.replace(/^---[\s\S]*?---/, "").trim().split("\n");
  const out: string[] = [];
  let inList = false;
  for (const raw of lines) {
    const line = esc(raw);
    if (/^\s*[-*]\s+/.test(raw)) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`);
      continue;
    }
    if (inList) { out.push("</ul>"); inList = false; }
    if      (/^###\s/.test(raw)) out.push(`<h4>${inline(line.replace(/^###\s/, ""))}</h4>`);
    else if (/^##\s/.test(raw))  out.push(`<h3>${inline(line.replace(/^##\s/, ""))}</h3>`);
    else if (/^#\s/.test(raw))   out.push(`<h2>${inline(line.replace(/^#\s/, ""))}</h2>`);
    else if (raw.trim() === "")  out.push("");
    else out.push(`<p>${inline(line)}</p>`);
  }
  if (inList) out.push("</ul>");
  return out.join("\n");

  function inline(s: string): string {
    return s
      .replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink" role="link" tabindex="0">$1</span>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }
}

// ── Stub node shape for wiki-only entities (no graph node available) ─────────
function stubNode(name: string): GraphNode {
  return { id: name, name, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 };
}

// ── Navigation entry — either a real graph node or a stub ───────────────────
type NavEntry = GraphNode;

// ── Component ────────────────────────────────────────────────────────────────
export default function WikiDrawer({
  node,
  onClose,
  graph,
}: {
  node: GraphNode | null;
  onClose: () => void;
  /** Optional full graph used to resolve wikilink names → real nodes */
  graph?: { nodes: GraphNode[] };
}) {
  // History stack — current page is the last entry.
  const [history, setHistory] = useState<NavEntry[]>([]);
  const [content, setContent]  = useState<string>("");
  const [live, setLive]        = useState(true);
  const [loading, setLoading]  = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  const current = history[history.length - 1] ?? null;

  // When the external `node` prop changes (user clicked a map node), reset.
  useEffect(() => {
    if (!node) { setHistory([]); return; }
    setHistory([node]);
  }, [node?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch wiki content whenever `current` changes.
  useEffect(() => {
    if (!current) return;
    setLoading(true);
    setContent("");
    // Scroll body back to top on navigation.
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
    api.wiki(current.name).then((env) => {
      setContent(env.data.content || `_No wiki page found for **${current.name}**._`);
      setLive(env.live);
      setLoading(false);
    });
  }, [current?.id ?? current?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  function navigateTo(name: string) {
    // Try to resolve to a real graph node for richer metadata.
    const match =
      graph?.nodes.find((n) => n.name.toLowerCase() === name.toLowerCase()) ??
      graph?.nodes.find(
        (n) =>
          n.name.toLowerCase().includes(name.toLowerCase()) ||
          name.toLowerCase().includes(n.name.toLowerCase())
      ) ??
      stubNode(name);
    setHistory((h) => [...h, match]);
  }

  function goBack() {
    setHistory((h) => (h.length > 1 ? h.slice(0, -1) : h));
  }

  const canGoBack = history.length > 1;
  const isOpen    = !!current;

  return createPortal(
    <aside className={`wd${isOpen ? " open" : ""}`} aria-hidden={!isOpen}>
      {current && (
        <>
          <div className="wd-head">
            <div className="wd-head-left">
              {canGoBack && (
                <button
                  className="wd-back press"
                  onClick={goBack}
                  aria-label="Go back"
                  title="Back"
                >
                  ←
                </button>
              )}
              <div>
                <div className="wd-type label-sm">{current.type}</div>
                <h2 className="wd-title">{current.name}</h2>
              </div>
            </div>
            <button className="wd-close press" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>

          {canGoBack && (
            <div className="wd-breadcrumb mono">
              {history.slice(0, -1).map((h, i) => (
                <span key={i}>
                  <button
                    className="wd-bc-btn"
                    onClick={() => setHistory((prev) => prev.slice(0, i + 1))}
                  >
                    {h.name}
                  </button>
                  <span className="wd-bc-sep"> › </span>
                </span>
              ))}
              <span className="wd-bc-current">{current.name}</span>
            </div>
          )}

          <div className="wd-meta">
            <Badge tone={bandTone(current.band)}>{current.band}</Badge>
            {current.score > 0 && (
              <span className="wd-meta-item mono">risk {(current.score * 100).toFixed(0)}%</span>
            )}
            {current.degree > 0 && (
              <span className="wd-meta-item mono">{current.degree} links</span>
            )}
            {!live && <span className="wd-offline mono">offline</span>}
          </div>

          <div className="wd-body" ref={bodyRef}>
            {loading ? (
              <div className="wd-skeleton">
                <span className="skeleton wd-sk-line" />
                <span className="skeleton wd-sk-line" />
                <span className="skeleton wd-sk-line short" />
              </div>
            ) : (
              <div
                dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
                onClick={(e) => {
                  const t = e.target as HTMLElement;
                  if (t.classList.contains("wikilink")) {
                    navigateTo(t.textContent ?? "");
                  }
                }}
                onKeyDown={(e) => {
                  const t = e.target as HTMLElement;
                  if ((e.key === "Enter" || e.key === " ") && t.classList.contains("wikilink")) {
                    navigateTo(t.textContent ?? "");
                  }
                }}
              />
            )}
          </div>

          <div className="wd-foot label-sm">
            Retrieved from SAGE knowledge base · not generated
          </div>
        </>
      )}
    </aside>,
    document.body
  );
}

function bandTone(band: string): "green" | "amber" | "coral" | "red" | "cyan" {
  return band === "CRITICAL" ? "red"
    : band === "ACTION"      ? "coral"
    : band === "ELEVATED"    ? "amber"
    : band === "WATCH"       ? "amber"
    : "green";
}
