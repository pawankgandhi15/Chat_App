import {useMemo, useState} from "react";
import {useChat} from "./useChat.js";
import {MessageList} from "./components/MessageList.jsx";
import {MessageComposer} from "./components/MessageComposer.jsx";
import {Icon} from "./components/Icon.jsx";
import {Avatar, Brand, StatusBadge} from "./components/ui.jsx";
import {ConversationTools} from "./components/ConversationTools.jsx";

function Sidebar({initialUsername, onName, state, contacts, onSelect, onSignIn}) {
  const [name, setName] = useState(initialUsername);
  return (
    <aside className="sidebar" aria-label="Room information">
      <div className="sidebar-top">
        <Brand caption="A little space to connect" />
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
            <Avatar name={peer.user} online={peer.online} />
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
          <Avatar name={name || "?"} className="profile-avatar" />
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

function ChatHeader({state, peer, onReconnect, onDisconnect, children}) {
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
        <StatusBadge id="status" connected={state.connected}>{state.status}</StatusBadge>
        <button id="reconnect" className="secondary connection-action" type="button" hidden={!canReconnect} onClick={onReconnect}>Reconnect</button>
        <button id="disconnect" className="quiet connection-action" type="button" hidden={canReconnect} onClick={onDisconnect}>Disconnect</button>
        {children}
      </div>
    </header>
  );
}

function Composer({state, peer, onDraft, onSend}) {
  return <MessageComposer label={peer ? `Message ${peer.user}` : "Message general"}
    placeholder={peer ? `Message ${peer.user}...` : "Write a message to the room..."}
    draft={state.draft} onDraft={onDraft} onSend={onSend}
    disabled={!state.connected || Boolean(peer && !peer.online)} busy={Boolean(state.pendingPrivate)}
    error={state.error ? state.notice : ""} notice={state.error ? "" : state.notice}
    privacy={peer ? "Only these sessions receive messages. Names are unverified; messages are not end-to-end encrypted." : "Messages are public to this room and aren’t saved as history."} />;
}

export function GuestApp({onSignIn}) {
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
          <ChatHeader state={chat.state} peer={peer} onReconnect={() => chat.connect()} onDisconnect={chat.disconnect}>
            <ConversationTools key={chat.state.conversation} name={peer?.user || "General"} direct={Boolean(peer)} connected={chat.state.connected}
              messages={messages.filter(event => event.type !== "system").map(event => ({id: event.event_id, text: event.text, sentAt: event.sent_at, author: event.user}))} />
          </ChatHeader>
          <MessageList key={chat.state.conversation} messages={messages} connected={chat.state.connected && (!peer || peer.online)}
            status={peer && !peer.online ? "Disconnected" : chat.state.status} peer={peer} />
          <Composer state={chat.state} peer={peer} onDraft={chat.setDraft} onSend={chat.send} />
        </main>
      </div>
    </>
  );
}
