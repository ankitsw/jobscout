import { useEffect, useRef, useState } from 'react';

export default function ChatPanel({ messages, onSend }) {
  const [input, setInput] = useState('');
  const threadRef = useRef(null);

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages]);

  function submit() {
    const text = input.trim();
    if (!text) return;
    setInput('');
    onSend(text);
  }

  return (
    <aside className="panel chat-panel">
      <div className="panel-header">
        <div className="panel-title">JobScout AI</div>
      </div>

      <div className="chat-thread" ref={threadRef}>
        {messages.map((message, index) => (
          <div className={`chat-bubble ${message.role}`} key={index}>{message.text}</div>
        ))}
      </div>

      <div className="chat-input-wrap">
        <input
          type="text"
          placeholder="Ask about this job..."
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') submit();
          }}
        />
        <button className="action-button" onClick={submit}>Send</button>
      </div>
    </aside>
  );
}
