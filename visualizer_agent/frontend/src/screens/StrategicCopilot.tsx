import { useRef, useState } from "react";
import { IconBot, IconSend, IconUser, IconBrain } from "../components/icons";
import { api } from "../api/hooks";
import type { CopilotAnswer } from "../api/types";
import "./copilot.css";

interface Msg {
  role: "user" | "sage";
  text: string;
  citations?: CopilotAnswer["citations"];
  live?: boolean;
}

const SUGGESTIONS = [
  "Why is ADNOC ranked first for Jamnagar?",
  "What is the current risk at the Strait of Hormuz?",
  "Summarise the Red Sea situation and its price impact.",
  "How many days of SPR cover remain under the Hormuz scenario?",
];

export default function StrategicCopilot() {
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      role: "sage",
      text: "Strategic Copilot online. I answer over SAGE's live knowledge graph — every response is grounded in source episodes and carries citations. How can I assist your assessment?",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const send = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    const { data, live } = await api.copilot(question);
    setMsgs((m) => [...m, { role: "sage", text: data.answer, citations: data.citations, live }]);
    setBusy(false);
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));
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
          {msgs.map((m, i) => (
            <div key={i} className={`cp-msg cp-msg-${m.role}`}>
              <div className="cp-avatar">
                {m.role === "sage" ? <IconBot width={16} height={16} /> : <IconUser width={16} height={16} />}
              </div>
              <div className="cp-bubble">
                <p>{m.text}</p>
                {m.citations && m.citations.length > 0 && (
                  <div className="cp-citations">
                    <span className="label-sm">Cited from graph</span>
                    <div className="cp-citation-chips">
                      {m.citations.map((c, j) => (
                        <span key={j} className="cp-citation">
                          {c.entity} <span className="mono cp-cite-id">{c.episode_id}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {m.live === false && <span className="cp-offline mono">backend offline — illustrative</span>}
              </div>
            </div>
          ))}
          {busy && (
            <div className="cp-msg cp-msg-sage">
              <div className="cp-avatar"><IconBot width={16} height={16} /></div>
              <div className="cp-bubble">
                <span className="cp-typing">
                  <span /><span /><span />
                </span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {msgs.length <= 1 && (
          <div className="cp-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="cp-suggestion" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        <form
          className="cp-input-row"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
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
    </div>
  );
}
