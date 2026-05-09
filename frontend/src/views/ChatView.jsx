import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { sendChat } from "../api/client";
import { chatStore } from "../store/chatStore";

export default function ChatView() {
  const [messages, setMessages] = useState(() => chatStore.messages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    const updated = [...messages, { role: "user", content: msg }];
    chatStore.messages = updated;
    setMessages(updated);
    setLoading(true);
    try {
      const { response } = await sendChat(msg, updated.slice(-10));
      setMessages((prev) => { const next = [...prev, { role: "assistant", content: response }]; chatStore.messages = next; return next; });
    } catch (e) {
      setMessages((prev) => { const next = [...prev, { role: "assistant", content: `Błąd: ${e.message}` }]; chatStore.messages = next; return next; });
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="chat-view">
      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            <div className="chat-bubble-label">{m.role === "user" ? "Ty" : "Agent"}</div>
            {m.role === "assistant" ? (
              <div className="chat-bubble-text chat-md">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              </div>
            ) : (
              <div className="chat-bubble-text" style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble assistant">
            <div className="chat-bubble-label">Agent</div>
            <div className="chat-bubble-text chat-typing">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          className="chat-input"
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Zapytaj o rynek… (Enter = wyślij, Shift+Enter = nowa linia)"
          disabled={loading}
        />
        <button className="chat-send-btn" onClick={send} disabled={loading || !input.trim()}>
          Wyślij
        </button>
      </div>
    </div>
  );
}
