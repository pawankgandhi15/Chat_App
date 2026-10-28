import {useCallback, useEffect, useMemo, useState} from "react";
import {AccountChat, AuthForm, api} from "./AccountChat.jsx";
import {useChat} from "./useChat.js";
import {MessageList} from "./components/MessageList.jsx";
import {Icon} from "./components/Icon.jsx";

function Sidebar({initialUsername, onName, state, contacts, onSelect, onSignIn}) {
  const [name, setName] = useState(initialUsername);
  return (
    <aside className="sidebar" aria-label="Room information">
      <div className="sidebar-top">
        <a className="brand" href="/" aria-label="Baatchit">
          <span className="brand-mark" aria-hidden="true"><Icon name="chat" /></span>
          <span>baatchit<span className="brand-period">.</span></span>
        </a>
        <span className="brand-caption">A little space to connect</span>
      </div>

      <div className="sidebar-content">
        <div className="section-label"><span>CONVERSATIONS</span><span className="section-count">01</span></div>
        <button type="button" className={"room" + (state.conversation === "general" ? " selected" : "")}
          aria-pressed={state.conversation === "general"} onClick={() => onSelect("general")}>
          <span className="room-icon"><Icon name="people" /></span>
          <span className="room-copy"><strong>General</strong><small>Public group room</small></span>
          <span className="room-arrow" aria-hidden="true">›</span>
        </button>

        <div className="sidebar-divider" />
        <div className="section-label"><span>DIRECT MESSAGES</span></div>
        <div className="peer-list" aria-label="People and direct conversations">
          {contacts.map(peer => <button type="button" key={peer.connection_id}
            className={"peer" + (state.conversation === peer.connection_id ? " selected" : "")}
            aria-pressed={state.conversation === peer.connection_id} onClick={() => onSelect(peer.connection_id)}>
            <span className="peer-avatar" aria-hidden="true">{peer.user.slice(0, 2).toUpperCase()}<span className={"peer-dot" + (peer.online ? " online" : "")} /></span>
            <span className="room-copy"><strong>{peer.user}</strong><small>{peer.online ? "Available" : "Offline"} · {peer.connection_id.slice(0, 6)}</small></span>
            {state.unread[peer.connection_id] > 0 && <span className="unread">{state.unread[peer.connection_id]}</span>}
          </button>)}
          {contacts.length === 0 && <div className="direct-message-info">
            <span className="direct-icon"><Icon name="people" /></span>
            <div><strong>{state.connected ? (state.protocol === "chat.v1" ? "Direct chats unavailable" : "No one here yet") : "Waiting to connect"}</strong>
              <p>{state.connected ? (state.protocol === "chat.v1" ? "This server supports General only" : "Online people appear here") : "Connect to see people"}</p></div>
          </div>}
        </div>
        <p className="sidebar-hint">Choose a person to start a direct chat. Names aren’t verified.</p>
      </div>

      <section className="profile" aria-labelledby="profile-title">
        <button className="account-invite secondary" onClick={onSignIn}>Sign in for saved chats</button>
        <div className="profile-heading">
          <span className="profile-avatar" aria-hidden="true">{(name || "?").slice(0, 2).toUpperCase()}</span>
          <div><h2 id="profile-title">Your display name</h2><p>Visible to everyone in the room</p></div>
        </div>
        <form id="profile-form" onSubmit={event => { event.preventDefault(); onName(name); }}>
          <label className="sr-only" htmlFor="username">Display name</label>
          <input id="username" name="username" maxLength={32} pattern={"[A-Za-z0-9_\\-]{1,32}"} required
            autoComplete="off" spellCheck={false} value={name} onChange={event => setName(event.target.value)} />
          <button type="submit" className="secondary">Update name</button>
        </form>
        <p className="profile-note">Names are temporary and aren’t verified.</p>
      </section>
    </aside>
  );
}

function ChatHeader({state, peer, onReconnect, onDisconnect}) {
  const canReconnect = ["Paused", "Disconnected", "Protocol error"].includes(state.status);
  return (
    <header className="chat-header">
      <div className="header-room">
        <span className="header-room-icon"><Icon name={peer ? "chat" : "people"} /></span>
        <div>
          <div className="title-row"><h1>{peer ? peer.user : "General"}</h1><span className="channel-tag">{peer ? "DIRECT CHAT" : "PUBLIC ROOM"}</span></div>
          <p>{peer ? (peer.online ? "Available · name is unverified" : "Offline · messages cannot be sent") : "A shared space for everyone"}</p>
        </div>
      </div>
      <div className="connection-controls">
        <span id="status" className="status" role="status" aria-live="polite" data-connected={state.connected}>{state.status}</span>
        <button id="reconnect" className="secondary connection-action" type="button" hidden={!canReconnect} onClick={onReconnect}>Reconnect</button>
        <button id="disconnect" className="quiet connection-action" type="button" hidden={canReconnect} onClick={onDisconnect}>Disconnect</button>
      </div>
    </header>
  );
}

function Composer({state, peer, onDraft, onSend}) {
  const empty = !state.draft.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, "");
  const available = state.connected && (!peer || peer.online);
  function onKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault();
      onSend();
    }
  }
  return (
    <footer className="composer-area">
      <div className="composer-inner">
        <p id="notice" className="notice" role="status" aria-live="polite" data-error={state.error}>{state.notice}</p>
        <form id="message-form" className="composer" onSubmit={event => { event.preventDefault(); onSend(); }}>
          <label className="sr-only" htmlFor="message">{peer ? `Message ${peer.user}` : "Message general"}</label>
          <textarea id="message" rows={2} placeholder={peer ? `Message ${peer.user}...` : "Write a message to the room..."} aria-describedby="composer-help counter"
            disabled={!available} value={state.draft} onChange={event => onDraft(event.target.value)} onKeyDown={onKeyDown} />
          <button id="send" className="send" type="submit" disabled={!available || empty || Boolean(state.pendingPrivate)}>
            <span>Send</span><Icon name="send" />
          </button>
        </form>
        <div className="composer-meta">
          <span id="composer-help"><kbd>Enter</kbd> to send <span aria-hidden="true">·</span> <kbd>Shift + Enter</kbd> for a new line</span>
          <span id="counter">{[...state.draft].length.toLocaleString()} / 2,000</span>
        </div>
        <p className="privacy-note"><Icon name="info" /> {peer ? "Only these sessions receive messages. Names are unverified; messages are not end-to-end encrypted." : "Messages are public to this room and aren’t saved as history."}</p>
      </div>
    </footer>
  );
}

function GuestApp({onSignIn}) {
  const chat = useChat();
  const contacts = useMemo(() => {
    const map = new Map();
    for (const [id, user] of Object.entries(chat.state.knownPeers)) map.set(id, {connection_id: id, user, online: false});
    for (const event of chat.state.messages) if (event.peer_id) map.set(event.peer_id, {connection_id: event.peer_id, user: event.peer_user, online: false});
    for (const peer of chat.state.peers) map.set(peer.connection_id, {...peer, online: true});
    return [...map.values()].sort((a, b) => Number(b.online) - Number(a.online) || a.user.localeCompare(b.user) || a.connection_id.localeCompare(b.connection_id));
  }, [chat.state.peers, chat.state.messages, chat.state.knownPeers]);
  const peer = chat.state.conversation === "general" ? null : contacts.find(item => item.connection_id === chat.state.conversation);
  const messages = useMemo(() => chat.state.messages.filter(event => chat.state.conversation === "general"
    ? event.type !== "private" : event.type === "private" && event.peer_id === chat.state.conversation),
  [chat.state.messages, chat.state.conversation]);
  return (
    <>
      <a className="skip-link" href="#message">Skip to message</a>
      <div className="app-shell">
        <Sidebar initialUsername={chat.initialUsername} onName={chat.connect} state={chat.state} contacts={contacts} onSelect={chat.selectConversation} onSignIn={onSignIn} />
        <main className="chat">
          <ChatHeader state={chat.state} peer={peer} onReconnect={() => chat.connect()} onDisconnect={chat.disconnect} />
          <MessageList key={chat.state.conversation} messages={messages} connected={chat.state.connected && (!peer || peer.online)}
            status={peer && !peer.online ? "Disconnected" : chat.state.status} peer={peer} />
          <Composer state={chat.state} peer={peer} onDraft={chat.setDraft} onSend={chat.send} />
        </main>
      </div>
    </>
  );
}

export function App() {
  const [user, setUser] = useState(null);
  const [auth, setAuth] = useState(false);
  const [authError, setAuthError] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let active = true;
    api("/auth/me").then(data => {if (active) setUser(data.user);}).catch(() => {})
      .finally(() => {if (active) setReady(true);});
    return () => {active = false;};
  }, []);
  const expired = useCallback(() => {
    setUser(null); setAuth(true); setAuthError("Your session expired. Sign in again to see your saved conversations.");
  }, []);
  if (!ready) return <main className="auth-page"><p role="status">Opening Baatchit…</p></main>;
  if (user) return <AccountChat key={user.id} user={user} onExpired={expired} onLogout={() => setUser(null)} />;
  if (auth) return <AuthForm initialError={authError} onSuccess={account => {setUser(account); setAuth(false); setAuthError("");}} onCancel={() => setAuth(false)} />;
  return <GuestApp onSignIn={() => {setAuth(true); setAuthError("");}} />;
}
