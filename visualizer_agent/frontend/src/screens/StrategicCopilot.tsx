import { useRef, useState } from "react";
import { IconBot, IconSend, IconUser, IconBrain } from "../components/icons";
import { MarkdownBody } from "../components/copilot/MarkdownBody";
import WikiDrawer from "../components/WikiDrawer";
import { api } from "../api/hooks";
import type { CopilotAnswer, CopilotSource, GraphNode } from "../api/types";
import "./copilot.css";

interface UserMsg { role: "user"; text: string }
interface SageMsg { role: "sage"; answer: CopilotAnswer; live: boolean }
type Msg = UserMsg | SageMsg;

const SUGGESTIONS = [
  "Compare India's alternative crude suppliers if Hormuz closes",
  "Why is the Strait of Hormuz critical for India?",
  "Is NIOC sanctioned, and by whom?",
  "How would a Hormuz closure cascade to Jamnagar and the SPR?",
];

// Open the wiki drawer for a cited entity (explainability — see the source).
function sourceToNode(entity: string, type: string): GraphNode {
  return { id: entity, name: entity, type, lat: null, lon: null, score: 0, band: "CALM", degree: 0 };
}

export default function StrategicCopilot() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [drawerNode, setDrawerNode] = useState<GraphNode | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const send = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    const { data, live } = await api.copilot(question);
    setMsgs((m) => [...m, { role: "sage", answer: data, live }]);
    setBusy(false);
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));
  };

  const openSource = (s: CopilotSource) => {
    if (s.kind === "wiki") setDrawerNode(sourceToNode(s.entity, s.type));
  };

  return (
    <div className="cp">
      <div className="cp-main">
        <div className="cp-header">
          <span className="cp-header-title">
            <IconBot width={20} height={20} className="c-cyan" /> Strategic Copilot
          </span>
          <span className="cp-router mono">
            <IconBrain width={13} height={13} /> EA-GraphRAG router · HippoRAG 2 PPR
          </span>
        </div>

        <div className="cp-thread">
          {msgs.length === 0 && (
            <div className="cp-empty">
              <div className="cp-empty-icon"><IconBot width={26} height={26} /></div>
              <h2>Ask SAGE anything</h2>
              <p>Grounded in the live knowledge graph — every answer is cited to entities and graph facts.</p>
            </div>
          )}

          {msgs.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="cp-msg cp-msg-user">
                <div className="cp-avatar"><IconUser width={16} height={16} /></div>
                <div className="cp-bubble">{m.text}</div>
              </div>
            ) : (
              <SageAnswer key={i} msg={m} onCite={openSource} />
            )
          )}

          {busy && (
            <div className="cp-msg cp-msg-sage">
              <div className="cp-avatar"><IconBot width={16} height={16} /></div>
              <div className="cp-answer">
                <div className="cp-searching">
                  <span className="cp-typing"><span /><span /><span /></span>
                  Searching the knowledge graph…
                </div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {msgs.length === 0 && (
          <div className="cp-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="cp-suggestion" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}

        <form className="cp-input-row" onSubmit={(e) => { e.preventDefault(); send(input); }}>
          <input
            className="cp-input"
            placeholder="Ask SAGE about risk, routes, reserves, or scenarios…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button className="cp-send" type="submit" disabled={busy || !input.trim()}>
            <IconSend width={17} height={17} />
          </button>
        </form>
      </div>

      <WikiDrawer node={drawerNode} onClose={() => setDrawerNode(null)} />
    </div>
  );
}

function SageAnswer({ msg, onCite }: { msg: SageMsg; onCite: (s: CopilotSource) => void }) {
  const { answer, live } = msg;
  const [copied, setCopied] = useState(false);
  const routeLabel = answer.route === "graph" ? "Graph PPR (multi-hop)" : answer.route === "vector" ? "Vector + BM25" : "Hybrid";

  const copy = () => {
    navigator.clipboard.writeText(answer.answer.replace(/\[\d+\]/g, "")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <div className="cp-msg cp-msg-sage">
      <div className="cp-avatar"><IconBot width={16} height={16} /></div>
      <div className="cp-answer">
        {/* Route / provenance strip */}
        <div className="cp-route">
          <span className={`cp-route-badge ${answer.route}`}>{routeLabel}</span>
          {answer.latency_ms != null && (
            <span className="cp-route-meta mono">{(answer.latency_ms / 1000).toFixed(1)}s</span>
          )}
          {!live && <span className="cp-route-meta mono c-amber">offline</span>}
        </div>

        <MarkdownBody text={answer.answer} sources={answer.sources} onCite={onCite} />

        {/* Sources (Perplexity-style numbered, clickable) */}
        {answer.sources.length > 0 && (
          <div className="cp-sources">
            <div className="cp-sources-head label-sm">
              Sources · {answer.sources.length}
            </div>
            <div className="cp-source-list">
              {answer.sources.map((s) => (
                <button
                  key={s.index}
                  className={`cp-source ${s.kind}`}
                  onClick={() => onCite(s)}
                  title={s.kind === "wiki" ? "Open wiki assessment" : s.snippet ?? ""}
                >
                  <span className="cp-source-num">{s.index}</span>
                  <span className="cp-source-body">
                    <span className="cp-source-title">{s.entity}</span>
                    <span className="cp-source-meta">
                      {s.type} · {s.kind === "wiki" ? "wiki assessment" : "graph fact"}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Action bar */}
        <div className="cp-actions">
          <button className="cp-action" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
        </div>
      </div>
    </div>
  );
}
