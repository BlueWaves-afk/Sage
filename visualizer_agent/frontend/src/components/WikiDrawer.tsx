import { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/hooks";
import { Badge } from "./ui/ui";
import type { GraphNode } from "../api/types";
import "./wikidrawer.css";

// ── Markdown renderer ────────────────────────────────────────────────────────
function renderMarkdown(md: string): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Strip YAML front-matter
  const body = md.replace(/^---[\s\S]*?---\n?/, "").trim();
  const lines = body.split("\n");
  const out: string[] = [];
  let inList = false;
  let inTable = false;
  let tableHeaderDone = false;

  function closeList() { if (inList) { out.push("</ul>"); inList = false; } }
  function closeTable() { if (inTable) { out.push("</tbody></table>"); inTable = false; tableHeaderDone = false; } }

  for (const raw of lines) {
    // ── Tables ──────────────────────────────────────────────────────────────
    if (/^\s*\|/.test(raw)) {
      closeList();
      const cells = raw.split("|").slice(1, -1).map((c) => c.trim());
      // Separator row (---|---|---)
      if (cells.every((c) => /^[-: ]+$/.test(c))) {
        tableHeaderDone = true;
        continue;
      }
      if (!inTable) {
        out.push('<table class="wd-table">');
        inTable = true;
        tableHeaderDone = false;
        // First row = header
        out.push("<thead><tr>" + cells.map((c) => `<th>${inline(esc(c))}</th>`).join("") + "</tr></thead><tbody>");
      } else {
        out.push("<tr>" + cells.map((c) => `<td>${inline(esc(c))}</td>`).join("") + "</tr>");
      }
      continue;
    }
    closeTable();

    // ── Lists ────────────────────────────────────────────────────────────────
    if (/^\s*[-*]\s+/.test(raw)) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${inline(esc(raw).replace(/^\s*[-*]\s+/, ""))}</li>`);
      continue;
    }
    closeList();

    // ── Headings & paragraphs ────────────────────────────────────────────────
    const line = esc(raw);
    if      (/^###\s/.test(raw)) out.push(`<h4>${inline(line.replace(/^###\s/, ""))}</h4>`);
    else if (/^##\s/.test(raw))  out.push(`<h3>${inline(line.replace(/^##\s/, ""))}</h3>`);
    else if (/^#\s/.test(raw))   out.push(`<h2>${inline(line.replace(/^#\s/, ""))}</h2>`);
    else if (raw.trim() === "")  out.push("");
    else out.push(`<p>${inline(line)}</p>`);
  }
  closeList();
  closeTable();
  return out.join("\n");

  function inline(s: string): string {
    return s
      // External markdown links [text](url) → anchor opening in new tab
      .replace(
        /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
        '<a class="wd-ext-link" href="$2" target="_blank" rel="noreferrer">$1 ↗</a>',
      )
      // Wiki internal links [[Entity]]
      .replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink" role="link" tabindex="0">$1</span>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }
}

function stubNode(name: string): GraphNode {
  return { id: name, name, type: "Entity", lat: null, lon: null, score: 0, band: "CALM", degree: 0 };
}

type NavEntry = GraphNode;

// ── Component ────────────────────────────────────────────────────────────────
export default function WikiDrawer({
  node,
  onClose,
  graph,
  onNavigate,
}: {
  node: GraphNode | null;
  onClose: () => void;
  graph?: { nodes: GraphNode[] };
  onNavigate?: (node: GraphNode) => void;
}) {
  const [history, setHistory] = useState<NavEntry[]>([]);
  const [content, setContent] = useState<string>("");
  const [live, setLive]       = useState(true);
  const [loading, setLoading] = useState(false);
  // Direction: +1 = forward (new link), -1 = back
  const [dir, setDir] = useState<1 | -1>(1);
  const bodyRef = useRef<HTMLDivElement>(null);

  const current = history[history.length - 1] ?? null;

  // External node change → reset history.
  useEffect(() => {
    if (!node) { setHistory([]); return; }
    setHistory([node]);
    setDir(1);
  }, [node?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch content whenever current page changes.
  useEffect(() => {
    if (!current) return;
    setLoading(true);
    setContent("");
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
    api.wiki(current.name).then((env) => {
      setContent(
        env.data?.content ||
          (env.live
            ? `_No wiki page found for **${current.name}**._`
            : `_Knowledge base offline — cannot load **${current.name}**._`),
      );
      setLive(env.live);
      setLoading(false);
    });
  }, [current?.id ?? current?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  function resolve(name: string): NavEntry {
    return (
      graph?.nodes.find((n) => n.name.toLowerCase() === name.toLowerCase()) ??
      graph?.nodes.find(
        (n) =>
          n.name.toLowerCase().includes(name.toLowerCase()) ||
          name.toLowerCase().includes(n.name.toLowerCase())
      ) ??
      stubNode(name)
    );
  }

  function navigateTo(name: string) {
    const match = resolve(name);
    const cur = history[history.length - 1];
    // Skip if already on the same page.
    if (cur && (cur.id === match.id || cur.name.toLowerCase() === match.name.toLowerCase())) return;
    setDir(1);
    setHistory((h) => [...h, match]);
    // Call onNavigate outside setHistory so it fires as a normal side-effect,
    // not inside a state-setter callback (which React can defer/batch unexpectedly).
    onNavigate?.(match);
  }

  function goBackTo(index: number) {
    const target = history[index];
    if (!target) return;
    setDir(-1);
    setHistory((h) => h.slice(0, index + 1));
    onNavigate?.(target);
  }

  function goBack() {
    if (history.length > 1) goBackTo(history.length - 2);
  }

  const canGoBack = history.length > 1;
  const isOpen    = !!current;

  // Variants for the drawer panel sliding in from the right.
  const drawerVariants = {
    hidden:  { x: "100%", opacity: 0 },
    visible: { x: 0, opacity: 1, transition: { type: "spring" as const, stiffness: 320, damping: 34, mass: 0.8 } },
    exit:    { x: "100%", opacity: 0, transition: { duration: 0.22, ease: "easeIn" as const } },
  };

  const pageVariants = {
    enter: (d: number) => ({ x: d > 0 ? 32 : -32, opacity: 0 }),
    center:              { x: 0, opacity: 1, transition: { duration: 0.22, ease: "easeOut" as const } },
    exit:  (d: number) => ({ x: d > 0 ? -32 : 32, opacity: 0, transition: { duration: 0.16, ease: "easeIn" as const } }),
  };

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.aside
          key="wd"
          className="wd open"
          variants={drawerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          aria-modal
          role="dialog"
        >
          {/* ── Header ── */}
          <div className="wd-head">
            <div className="wd-head-left">
              <AnimatePresence>
                {canGoBack && (
                  <motion.button
                    key="back"
                    className="wd-back press"
                    onClick={goBack}
                    aria-label="Go back"
                    title="Back"
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0, transition: { duration: 0.18 } }}
                    exit={{ opacity: 0, x: -8, transition: { duration: 0.12 } }}
                  >
                    ←
                  </motion.button>
                )}
              </AnimatePresence>
              <div>
                <div className="wd-type label-sm">{current.type}</div>
                <h2 className="wd-title">{current.name}</h2>
              </div>
            </div>
            <button className="wd-close press" onClick={onClose} aria-label="Close">✕</button>
          </div>

          {/* ── Breadcrumb ── */}
          <AnimatePresence>
            {canGoBack && (
              <motion.div
                key="bc"
                className="wd-breadcrumb mono"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto", transition: { duration: 0.2 } }}
                exit={{ opacity: 0, height: 0, transition: { duration: 0.14 } }}
              >
                {history.slice(0, -1).map((h, i) => (
                  <span key={i}>
                    <button className="wd-bc-btn" onClick={() => goBackTo(i)}>
                      {h.name}
                    </button>
                    <span className="wd-bc-sep"> › </span>
                  </span>
                ))}
                <span className="wd-bc-current">{current.name}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Meta ── */}
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

          {/* ── Body — slides left/right on navigation ── */}
          <div className="wd-body" ref={bodyRef}>
            <AnimatePresence mode="wait" custom={dir}>
              <motion.div
                key={current.id ?? current.name}
                custom={dir}
                variants={pageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                style={{ height: "100%" }}
              >
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
                      if (t.classList.contains("wikilink")) navigateTo(t.textContent ?? "");
                    }}
                    onKeyDown={(e) => {
                      const t = e.target as HTMLElement;
                      if ((e.key === "Enter" || e.key === " ") && t.classList.contains("wikilink")) {
                        navigateTo(t.textContent ?? "");
                      }
                    }}
                  />
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          <div className="wd-foot label-sm">
            Retrieved from SAGE knowledge base · not generated
          </div>
        </motion.aside>
      )}
    </AnimatePresence>,
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
