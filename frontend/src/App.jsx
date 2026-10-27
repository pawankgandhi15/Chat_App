import {useState} from "react";
import {useChat} from "./useChat.js";
import {MessageList} from "./components/MessageList.jsx";

function Sidebar({initialUsername, onName}) {
  const [name, setName] = useState(initialUsername);
  return (
    <aside className="sidebar" aria-label="Room information">
      <a className="brand" href="/"><span className="brand-mark" aria-hidden="true">b.</span><span>Baatchit</span></a>
      <p className="eyebrow">A little space to connect</p>
      <div className="room">
        <span className="hash" aria-hidden="true">#</span>
        <div><strong>general</strong><small>One room. Everyone welcome.</small></div>
        <span className="room-dot" />
      </div>
      <section className="profile" aria-labelledby="profile-title">
        <h2 id="profile-title">Your display name</h2>
        <form id="profile-form" onSubmit={event => { event.preventDefault(); onName(name); }}>
          <label className="sr-only" htmlFor="username">Display name</label>
          <input id="username" name="username" maxLength={32} pattern={"[A-Za-z0-9_\\-]{1,32}"} required
            autoComplete="off" spellCheck={false} value={name} onChange={event => setName(event.target.value)} />
          <button type="submit" className="secondary">Update name</button>
        </form>
        <p className="micro">A temporary name, not a verified identity.</p>
      </section>
      <div className="sidebar-bottom">
        <span className="small-icon" aria-hidden="true">◎</span>
        <h2>Here for the moment.</h2>
        <p>Messages are live and temporary. There’s no account, inbox, or saved history.</p>
        <span className="version">CHAT.V1 · LIVE CONVERSATIONS</span>
      </div>
    </aside>
  );
}

function ChatHeader({state, onReconnect, onDisconnect}) {
  const canReconnect = ["Paused", "Disconnected", "Protocol error"].includes(state.status);
  return (
    <header className="chat-header">
      <div>
        <div className="title-row"><span className="hash" aria-hidden="true">#</span><h1>general</h1><span className="channel-tag">PUBLIC ROOM</span></div>
        <p>A shared conversation, happening now.</p>
      </div>
      <div className="connection-controls">
        <span id="status" className="status" role="status" aria-live="polite" data-connected={state.connected}>{state.status}</span>
        <button id="reconnect" className="secondary" type="button" hidden={!canReconnect} onClick={onReconnect}>Reconnect</button>
        <button id="disconnect" className="quiet" type="button" hidden={canReconnect} onClick={onDisconnect}>Disconnect</button>
      </div>
    </header>
  );
}

function Composer({state, onDraft, onSend}) {
  const empty = !state.draft.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, "");
  function onKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault();
      onSend();
    }
  }
  return (
    <footer className="composer-area">
      <p id="notice" className="notice" role="status" aria-live="polite" data-error={state.error}>{state.notice}</p>
      <form id="message-form" className="composer" onSubmit={event => { event.preventDefault(); onSend(); }}>
        <label className="sr-only" htmlFor="message">Message general</label>
        <textarea id="message" rows={2} placeholder="Message #general" aria-describedby="composer-help counter"
          disabled={!state.connected} value={state.draft} onChange={event => onDraft(event.target.value)} onKeyDown={onKeyDown} />
        <button id="send" className="send" type="submit" disabled={!state.connected || empty}>
          <span>Send</span><span aria-hidden="true">↗</span>
        </button>
      </form>
      <div className="composer-meta">
        <span id="composer-help"><kbd>Enter</kbd> to send · <kbd>Shift + Enter</kbd> for a new line</span>
        <span id="counter">{[...state.draft].length.toLocaleString()} / 2,000</span>
      </div>
      <p className="privacy-note">Live only. Messages missed while disconnected cannot be recovered. Never share sensitive information.</p>
    </footer>
  );
}

export function App() {
  const chat = useChat();
  return (
    <>
      <a className="skip-link" href="#message">Skip to message</a>
      <div className="app-shell">
        <Sidebar initialUsername={chat.initialUsername} onName={chat.connect} />
        <main className="chat">
          <ChatHeader state={chat.state} onReconnect={() => chat.connect()} onDisconnect={chat.disconnect} />
          <MessageList messages={chat.state.messages} />
          <Composer state={chat.state} onDraft={chat.setDraft} onSend={chat.send} />
        </main>
      </div>
    </>
  );
}
