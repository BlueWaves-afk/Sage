# SAGE Live — Voice Interface Design Spec (System 6)

**Status:** Design only — not yet implemented. This is the spec to build against.
**Owner:** Voice/UX
**Depends on:** System 5 frontend (routes, WikiDrawer, KnowledgeGraphMap), the
Strategic Copilot's EA-GraphRAG engine (`knowledge/api/read.py::copilot_query`),
and the API gateway (`visualizer_agent/api_gateway`).

---

## 0. One-paragraph summary

A hands-free, full-duplex voice layer ("Sage Live") sits on top of the existing
SAGE frontend. The user says a wake phrase ("Hey Sage"), speaks naturally, and
SAGE responds by voice **while also driving the UI** — switching tabs, opening
the wiki drawer on the entity being discussed, running a scenario, focusing the
map on a corridor, or flashing the KPI the user asked about. The voice pipeline
does not replace the Strategic Copilot's text engine — it's a second front end
onto the *same* answer engine (`copilot_query`) plus a thin "voice action"
layer that a text chat doesn't need (navigation, highlighting, live numbers).

---

## 1. Provider: Gnani (Inya VoiceOS)

Confirmed from Gnani's public docs (not guessed):

| Component | Model | Notes |
|---|---|---|
| STT | Vachana / Prisma v2.5 | Real-time streaming over WebSocket, VAD-driven turn detection, p95 ≈ 200ms, 12 languages incl. Indian English + Hinglish code-mixed modes |
| TTS | Vachana / Timbre v2.0 | Streams PCM audio chunks before the full sentence finishes synthesizing (true low-latency streaming, not "generate then play") |
| Integration | `livekit-plugins-gnani` (official) | A thin adapter wrapping Gnani STT/TTS into LiveKit Agents' `stt.STT` / `tts.TTS` base classes — LiveKit manages the WebSocket/WebRTC plumbing, not us |

**Why LiveKit, not a hand-rolled WebSocket audio pipe:** LiveKit Agents is the
same class of framework Gemini Live-style products are built on. It gives us,
for free, the three hardest parts of "live conversational AI":
1. **WebRTC transport** — far better than raw WebSocket for browser mic audio
   (jitter buffering, echo cancellation, adaptive bitrate, NAT traversal).
2. **Turn-taking + barge-in** — if the user starts talking while SAGE's TTS is
   playing, LiveKit's VAD interrupts the agent's audio automatically. This is
   the single hardest UX problem in "live" voice AI and we get it out of the box.
2. **Data channel** — a side-channel in the same WebRTC room lets the Python
   agent push structured JSON events ("navigate to /intelligence", "highlight
   Strait of Hormuz") to the browser in lockstep with the audio, which is
   exactly the mechanism that drives "tabs change, diagrams pop up."

Do **not** attempt to stream raw audio from the browser directly to Gnani's
WebSocket with the API key embedded client-side — the key must only ever be
held by the Python agent process (server-side). This is already reflected in
`.env` (`GNANI_API_KEY`, not exposed to the frontend build).

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Browser (visualizer_agent/frontend)                                      │
│                                                                            │
│  VoiceOrbProvider (mounted once, in AppShell — persists across routes)    │
│    │                                                                      │
│    ├─ Local wake-word engine (Porcupine WASM, "Hey Sage")                │
│    │    → runs ENTIRELY client-side, no audio leaves the browser          │
│    │    → on detect: join LiveKit room, publish mic track                 │
│    │                                                                      │
│    ├─ livekit-client SDK                                                  │
│    │    → publishes mic audio track to the room                          │
│    │    → subscribes to the agent's synthesized speech audio track       │
│    │    → listens on the room DataChannel for voice-action JSON events   │
│    │                                                                      │
│    ├─ VoiceOrb.tsx — floating orb, states: idle/listening/thinking/       │
│    │    speaking, with a live waveform driven by mic amplitude            │
│    │                                                                      │
│    └─ voiceActions.ts — the action bus. Receives {type, payload} from the │
│         data channel, executes it against the app's real state:           │
│         navigate(), setFocusedEntity(), triggerScenarioRun(), etc.        │
└─────────────────────────────────────────────────────────────────────────┘
                    │ WebRTC (audio + data channel)
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LiveKit server (self-hosted OSS, or LiveKit Cloud free tier)              │
│  — room = one voice session. Issues short-lived JWTs (our backend signs   │
│    these; browser never sees a static credential).                       │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ voicebridge/ (new Python service — a LiveKit Agent worker)                │
│                                                                            │
│  1. STT   — livekit-plugins-gnani (Prisma v2.5), streaming, VAD-gated     │
│  2. Brain — voicebridge/intent.py: classifies the transcript (see §4)     │
│       ├─ nav/action intent  → emit a VoiceAction over the data channel    │
│       └─ data-query intent → call knowledge.api.read.copilot_query()     │
│                                (THE SAME function powering the text       │
│                                Strategic Copilot — one answer engine)     │
│  3. Speakable-answer step — strips markdown/citations down to a short,    │
│     TTS-appropriate sentence (voicebridge/speakable.py)                   │
│  4. TTS   — livekit-plugins-gnani (Timbre v2.0), streams back into the    │
│     room as the agent's audio track                                      │
│                                                                            │
│  Runs as its own container (docker-compose service `voice-agent`),        │
│  imports knowledge/* directly (same KB the API gateway uses) — no HTTP    │
│  hop needed for data queries.                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Hands-free activation model

Genuine hands-free means the mic is never actively *streamed to a paid API*
until the user has clearly signalled intent — otherwise every session is
continuously billing Gnani and raising a real privacy question ("is this
always listening?").

**Design: local wake-word, not always-on streaming.**

- Client runs a WASM wake-word model (Picovoice Porcupine has a free tier for
  a custom keyword — train "Hey Sage" once, ship the `.ppn` model file with
  the frontend bundle). This runs **entirely in the browser**, no network
  call, negligible CPU.
- On wake-word detection: `VoiceOrb` transitions `idle → listening`, joins the
  LiveKit room (or unmutes an already-joined-but-muted track), and starts
  streaming to the agent.
- End of turn: Gnani's STT VAD detects trailing silence (~700ms) and finalizes
  the transcript; the agent processes it, speaks/acts, then the client
  auto-returns to `idle` (wake-word-only) after a short window — no user click
  needed for a multi-turn conversation ("what about Suez Canal?" works without
  re-saying the wake word, using a ~6s open-mic follow-up window after SAGE
  finishes speaking, matching how Gemini Live keeps the floor open briefly).
- **Escape hatches** (required, not optional): a visible mute toggle in the
  orb at all times, and a "Stop listening" voice command that's handled
  locally (no round-trip) for instant, trustworthy silence.
- **Fallback mode**: push-to-talk (hold the orb / spacebar) for noisy
  environments or when wake-word models aren't trained/available yet in dev —
  ship this first, wake-word second, so the feature works end-to-end before
  the wake-word polish lands.

---

## 4. Command taxonomy — the part that makes "diagrams pop up"

The Brain step classifies every transcript into one of four intent classes.
Classification should be a **fast model** (Nova Micro, same one triage.py
already uses) with a small, versioned prompt — not a generic LLM chat loop —
because latency here is the dominant contributor to the "does this feel live"
perception.

| Intent class | Example utterance | Resulting VoiceAction | Spoken response |
|---|---|---|---|
| **Navigate** | "Show me the command center" / "Go to the map" | `{type:"navigate", route:"/command"}` | "Command Center." (terse ack) |
| **Focus entity** | "Show me the Strait of Hormuz" / "Zoom into Jamnagar" | `{type:"navigate", route:"/intelligence"}` then `{type:"focus_entity", entity:"Strait of Hormuz"}` | "Here's Strait of Hormuz — currently CRITICAL." |
| **Open wiki** | "Tell me more about ADNOC" / "What's the story on Jamnagar" | `{type:"open_wiki", entity:"ADNOC"}` (drawer opens wherever the user is) | reads the first 1-2 sentences of the Current Assessment aloud |
| **Run action** | "Run a Hormuz disruption scenario" | `{type:"navigate", route:"/simulation"}` then `{type:"run_scenario", trigger_entity:"Strait of Hormuz"}` (calls the same trigger path as `orchestration.graph.run_pipeline`/cold pipeline) | "Running it now — this'll take a few seconds." then a follow-up utterance once `write_scenario` completes: "Done — projected gap is 0.6 mbpd, price impact up to $61." |
| **KPI lookup** | "What's the SPR coverage?" / "What's the threat level?" | `{type:"flash_kpi", key:"spr_coverage_pct"}` (pulses that KPI tile) | speaks the real number from `/api/dashboard` — never invented |
| **Compare/rank** | "Why is ADNOC ranked first?" / "Compare the top two options" | `{type:"navigate", route:"/response"}` then `{type:"select_option", supplier:"ADNOC"}` (drives the radar exactly like a card click) | the copilot_query() answer, shortened for speech, with citation entities mentioned by name ("...according to the Jamnagar refinery assessment") instead of `[1]` markers |
| **Open-ended question** | "Why is Hormuz risky right now" / anything not matching the above | *(no UI action — text answer only)* | full `copilot_query()` route (vector or graph PPR), spoken |
| **Control** | "Stop" / "Cancel" / "Never mind" | handled **client-side**, no round trip: stops TTS playback immediately (barge-in also covers this, but an explicit command is a trust signal) | — |

**Design principle:** every number SAGE speaks must come from the same
`/api/dashboard`, `/api/scenario`, `/api/procurement`, `/api/spr-schedule`
endpoints the screens already read — the voice brain is a *router*, not a
second source of truth. If a screen would show a skeleton (no live data),
voice says so explicitly ("I don't have a live scenario yet") rather than
guessing.

---

## 5. Frontend integration points (what already exists to hook into)

| Screen | Voice action(s) it must handle |
|---|---|
| `AppShell.tsx` | Mounts `VoiceOrbProvider` once; owns `navigate()` for route-changing actions |
| `GlobalIntelligence.tsx` | `focus_entity` → select that node in `KnowledgeGraphMap`, fly the camera, open `WikiDrawer` |
| `CommandCenter.tsx` | `flash_kpi` → briefly pulse the matching `.cc-kpi` tile (reuse the existing `pulse-dot` keyframe already in `index.css`) |
| `SimulationLab.tsx` | `run_scenario` → call the same endpoint the "Execute Run" button would (needs wiring — currently that button is a no-op per earlier session notes) |
| `ResponsePlanner.tsx` | `select_option` → call the existing `setActiveSupplier()` state setter we just built for click-selection — voice and click drive the *same* state |
| `StrategicCopilot.tsx` | Voice conversation transcript can optionally append into the same message thread, so a user can start by voice and continue by typing |

This means the voice layer needs **no new UI capability** for entity focus,
KPI flashing (add one CSS class), or radar selection — it reuses
`setActiveSupplier`, `setSelected` (WikiDrawer), and the router's `navigate()`
that already exist from the click-driven interactions built earlier. The
action bus is just a second caller of those same functions.

**New shared module:** `visualizer_agent/frontend/src/voice/voiceActions.ts`
exports a single `applyVoiceAction(action: VoiceAction)` that a lightweight
global store (Zustand, no new dependency needed if we keep it to one small
store) dispatches to. Screens read from that store the same way they'd read
route params — no prop drilling from the orb.

---

## 6. Latency budget (targets, to validate once implemented)

| Stage | Budget | Source |
|---|---|---|
| Wake-word detect → mic live | <150ms | Porcupine WASM (client-only, no network) |
| Speech end → STT final transcript | ~200ms | Gnani Prisma v2.5 published p95 |
| Transcript → intent classified | ~150-300ms | Nova Micro, small prompt |
| Nav/action intents: → VoiceAction dispatched | ~50ms | data channel, same room, no HTTP |
| Data-query intents: → copilot_query() answer | 380ms (vector) / 1,800ms (graph PPR) | already measured in the existing Copilot |
| Speakable text → first TTS audio byte | ~150-250ms | Gnani Timbre streaming first-byte |
| **Nav/action round trip (perceived)** | **~0.6-1.0s** | comparable to Gemini Live's target band |
| **Data-query round trip (perceived)** | **~1.0-2.5s** | acceptable — Strategic Copilot already sets this expectation |

---

## 7. What to build, in order

1. **`voicebridge/` service** — LiveKit Agent worker: Gnani STT → intent
   classifier (heuristic first, Nova Micro second) → `copilot_query()` for
   data intents → speakable-text step → Gnani TTS. Ship push-to-talk only
   (no wake word yet) so the full round trip is provable end-to-end.
2. **LiveKit server** — self-hosted via `docker-compose` (official
   `livekit/livekit-server` image) alongside falkordb/redis, or LiveKit
   Cloud's free tier for the hackathon (fewer moving parts, faster to demo).
3. **Frontend: `VoiceOrbProvider` + `VoiceOrb.tsx`** — join room, publish mic
   on a press-and-hold button first (matches step 1's push-to-talk), play the
   agent's audio track, render listening/thinking/speaking states.
4. **`voiceActions.ts` action bus** — wire `navigate`, `focus_entity`,
   `open_wiki`, `flash_kpi`, `select_option`, `run_scenario` against the real
   functions/state setters listed in §5.
5. **Wake-word layer** — swap push-to-talk for Porcupine-driven hands-free
   activation once the round trip is validated. This is additive, not a
   rewrite of anything in steps 1-4.
6. **Multi-turn follow-up window + barge-in polish** — tune the ~6s open-mic
   window and confirm LiveKit's interruption behavior feels right in practice.

---

## 8. Explicit non-goals for v1

- **Not** replacing the Strategic Copilot's text UI — voice is an additional
  front end onto the same `copilot_query()` engine.
- **Not** implementing wake-word detection server-side — it must be
  client-local for the privacy/cost reasons in §3.
- **Not** attempting full Hinglish/multi-language support in v1, even though
  Gnani supports it — ship English-only first, it's a config change later
  (`language` param on the STT/TTS plugin), not an architecture change.
- **Not** giving voice write-access to anything System 1 will eventually own
  (no "add a sanction" or "change the risk score" by voice) — voice can
  *trigger* an existing, already-safe action (run a scenario) but never
  directly mutate the knowledge graph.

---

## 9. Manual setup steps (cannot be automated from here)

- Register a Gnani developer account (already have `GNANI_API_KEY` in `.env`
  — confirm with Gnani support whether this key also grants LiveKit-plugin
  access or if a separate token/cert pair is needed per their auth docs).
- Stand up a LiveKit server (self-hosted container or a free LiveKit Cloud
  project) and add its URL/API key/secret to `.env` alongside `GNANI_API_KEY`.
- Train the "Hey Sage" custom wake word via Picovoice's console (free tier)
  once ready to move past push-to-talk.
