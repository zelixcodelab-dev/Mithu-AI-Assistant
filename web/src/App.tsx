import { useCallback, useState } from "react";
import { useConversation } from "@elevenlabs/react";
import { AudioLines, Bot, Brain, Languages, Mic, MicOff, PhoneOff, ShieldCheck, Sparkles, Volume2 } from "lucide-react";

type AssistantMode = "personal" | "business";
type ChatLine = { role: "user" | "assistant"; text: string };

const API = (import.meta.env.VITE_MITHU_API_URL || "").replace(/\/$/, "");

export default function App() {
  const [mode, setMode] = useState<AssistantMode>("personal");
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [micReady, setMicReady] = useState(false);

  const onMessage = useCallback((event: any) => {
    const text = typeof event?.message === "string" ? event.message : "";
    if (!text.trim()) return;
    const role = event?.source === "user" ? "user" : "assistant";
    setLines((current) => [...current.slice(-39), { role, text }]);
  }, []);

  const conversation = useConversation({
    onMessage,
    onError: (event: any) => setError(event?.message || "Voice connection error. Please try again."),
    serverLocation: "in-residency",
  });

  const start = async () => {
    setError("");
    setBusy(true);
    try {
      const identity = await window.mithuAuth?.getIdentityAssertion();
      if (!identity) throw new Error("Mithu is not connected to an authenticated host. Open it through EduConnect or configure the authentication bridge.");
      await navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        stream.getTracks().forEach((track) => track.stop());
      });
      setMicReady(true);
      const response = await fetch(`${API}/api/v1/voice/session`, {
        method: "POST",
        headers: { "X-Mithu-Identity": identity },
        cache: "no-store",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Unable to create voice session (${response.status})`);
      }
      const session = await response.json();
      await conversation.startSession({ signedUrl: session.signed_url });
      conversation.sendContextualUpdate(
        mode === "personal"
          ? "Assistant mode: PERSONAL. Help with general questions, planning, learning, productivity and everyday tasks. Do not access EduConnect business records in this mode."
          : "Assistant mode: EDUCONNECT BUSINESS. Help with authorized EduConnect Pro workflows. Use only configured, permission-checked read-only business tools. Never claim an action was completed unless a tool confirms it."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start voice conversation.");
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    await conversation.endSession();
    setMicReady(false);
  };

  const changeMode = (next: AssistantMode) => {
    setMode(next);
    if (conversation.status === "connected") {
      conversation.sendContextualUpdate(
        next === "personal"
          ? "Switch to PERSONAL assistant mode. Do not access EduConnect business records."
          : "Switch to EDUCONNECT BUSINESS mode. Use only configured, permission-checked read-only business tools."
      );
    }
  };

  const connected = conversation.status === "connected";
  const speaking = conversation.isSpeaking;
  const listening = conversation.isListening;

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#"><span className="brand-mark"><AudioLines size={20}/></span><span>MITHU<span className="brand-ai">.AI</span></span></a>
        <div className="secure"><ShieldCheck size={15}/> Private voice session</div>
      </header>

      <section className="hero">
        <div className="eyebrow"><Sparkles size={14}/> YOUR REALTIME AI COMPANION</div>
        <h1>Meet <span>Mithu.</span></h1>
        <p className="subhead">A more natural way to think, ask, plan and get things done.</p>

        <div className="mode-switch" role="group" aria-label="Assistant mode">
          <button className={mode === "personal" ? "mode active" : "mode"} onClick={() => changeMode("personal")}><Brain size={16}/> Personal</button>
          <button className={mode === "business" ? "mode active" : "mode"} onClick={() => changeMode("business")}><Bot size={16}/> EduConnect</button>
        </div>

        <div className={`orb-wrap ${speaking ? "speaking" : ""} ${listening ? "listening" : ""}`}>
          <div className="orb-halo halo-one"/><div className="orb-halo halo-two"/>
          <div className="orb"><div className="orb-core"><AudioLines size={48} strokeWidth={1.25}/></div></div>
          <span className="orb-caption">{connected ? speaking ? "Mithu is speaking" : listening ? "Listening to you" : "Connected" : "Ready when you are"}</span>
        </div>

        <div className="status-line">
          <span className={connected ? "status-dot live" : "status-dot"}/>
          {busy ? "Preparing secure session…" : connected ? "Live conversation" : "Not connected"}
          <span className="status-divider">·</span><Languages size={14}/> Malayalam · Manglish · English
        </div>

        <div className="controls">
          {!connected ? (
            <button className="start-button" onClick={start} disabled={busy}>
              <Mic size={19}/>{busy ? "Connecting…" : "Start talking"}
            </button>
          ) : (
            <>
              <button className="icon-button" aria-label={conversation.isMuted ? "Unmute microphone" : "Mute microphone"} onClick={() => conversation.setMuted(!conversation.isMuted)}>
                {conversation.isMuted ? <MicOff size={19}/> : <Mic size={19}/>}
              </button>
              <button className="stop-button" onClick={stop}><PhoneOff size={18}/> End conversation</button>
              <button className="icon-button" aria-label="Adjust output volume" onClick={() => conversation.setVolume({ volume: 0.8 })}><Volume2 size={19}/></button>
            </>
          )}
        </div>
        {error && <div className="error" role="alert">{error}</div>}
        <p className="permission-note">Your microphone is activated only after you start a session.</p>
      </section>

      <section className="transcript">
        <div className="transcript-head"><span>CONVERSATION</span><span>{connected ? "LIVE" : "SESSION PREVIEW"}</span></div>
        {lines.length === 0 ? (
          <div className="empty"><div className="empty-icon"><Volume2 size={18}/></div><p>Your conversation will appear here.</p><span>Try saying “Hello Mithu, how can you help me?”</span></div>
        ) : (
          <div className="messages">{lines.map((line, index) => <div className={`message ${line.role}`} key={index}><span>{line.role === "user" ? "YOU" : "MITHU"}</span><p>{line.text}</p></div>)}</div>
        )}
      </section>

      <footer><span>Powered by ElevenLabs Conversational AI</span><span>Personal + Business · Separate EduConnect integration</span></footer>
    </main>
  );
}