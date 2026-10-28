import {useCallback, useEffect, useRef, useState} from "react";
import {Icon} from "./components/Icon.jsx";

export async function api(path, options = {}) {
  const response = await fetch("/api" + path, {credentials: "same-origin", ...options,
    signal: options.signal || AbortSignal.timeout(10000),
    headers: {"Content-Type": "application/json", ...options.headers}});
  let data;
  try { data = await response.json(); }
  catch { throw new Error("Saved chats need the backend and database. Please start the full app."); }
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "The request could not be completed.");
    error.status = response.status;
    throw error;
  }
  return data;
}

export function AuthForm({onSuccess, onCancel, initialError = ""}) {
  const [mode, setMode] = useState("login");
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      const data = await api("/auth/" + mode, {method: "POST", body: JSON.stringify(Object.fromEntries(form))});
      onSuccess(data.user);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <main className="auth-page"><section className="auth-card" aria-label="Account access">
    <span className="brand"><span className="brand-mark"><Icon name="chat" /></span>baatchit.</span>
    <span className="section-label">CONVERSATIONS THAT STAY WITH YOU</span>
    <h1>{mode === "login" ? "Welcome back." : "Your conversations start here."}</h1>
    <p>Sign in to find people, keep your conversations, and return to your message history.</p>
    <form onSubmit={submit}>
      <label htmlFor="account-username">Username</label>
      <input id="account-username" name="username" autoFocus autoComplete="username" required minLength={3} maxLength={32}
        pattern="[A-Za-z0-9_-]{3,32}" placeholder="e.g. pawan" />
      <small>3–32 letters, numbers, underscores or hyphens. Usernames are case-insensitive and searchable by signed-in users.</small>
      <label htmlFor="account-password">Password</label>
      <input id="account-password" name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"}
        required minLength={15} maxLength={128} />
      <small>Use 15–128 characters. Password recovery is not available yet.</small>
      <p role="alert" className="account-error">{error}</p>
      <button className="send" type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
    </form>
    <button className="quiet" disabled={busy} onClick={() => {setMode(mode === "login" ? "register" : "login"); setError("");}}>
      {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}</button>
    <button className="quiet" disabled={busy} onClick={onCancel}>Back to temporary guest chat</button>
  </section></main>;
}

export function AccountChat({user, onLogout, onExpired}) {
  const accountApi = useCallback((path, options = {}) => api(path, {...options,
    headers: {...options.headers, "X-Account-ID": user.id}}), [user.id]);
  const [conversations, setConversations] = useState([]);
  const [next, setNext] = useState(null);
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState({id: null, items: [], before: null});
  const [drafts, setDrafts] = useState({});
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyMode, setHistoryMode] = useState(false);
  const [live, setLive] = useState(false);
  const [revision, setRevision] = useState(0);
  const [readSeq, setReadSeq] = useState({});
  const pending = useRef(new Map());
  const sending = useRef(false);
  const alive = useRef(true);
  const listCursor = useRef(null);
  const listBusy = useRef(false);
  const messageArea = useRef(null);
  const followTail = useRef(true);
  const current = conversations.find(item => item.id === selected);
  const shown = history.id === selected ? history.items : [];
  const draft = drafts[selected] || "";
  function choose(id) {
    setSelected(id); setHistoryMode(false); setError(""); setNotice(""); followTail.current = true;
  }
  useEffect(() => {
    if (!historyMode && followTail.current && messageArea.current) messageArea.current.scrollTop = messageArea.current.scrollHeight;
  }, [shown.length, selected, historyMode]);
  const report = useCallback(failure => {
    if (!alive.current) return;
    if (failure.status === 401) onExpired();
    else setError(failure.name === "TimeoutError" ? "The request timed out. Your draft is kept; retry to check whether it was saved." : failure.message);
  }, [onExpired]);
  useEffect(() => {alive.current = true; return () => {alive.current = false;};}, []);

  const refreshConversations = useCallback(async () => {
    if (listBusy.current) return;
    listBusy.current = true;
    try {
      // Refresh every page already loaded; a reconnect can introduce new threads.
      let cursor = null, items = [], response;
      do {
        response = await accountApi("/conversations" + (cursor ? "?after=" + cursor : ""));
        items.push(...response.items);
        cursor = response.next_cursor;
      } while (cursor && listCursor.current && cursor <= listCursor.current);
      if (!alive.current) return;
      setConversations(old => {
        const map = new Map(old.map(item => [item.id, item]));
        for (const item of items) map.set(item.id, item);
        return [...map.values()].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      });
      setNext(cursor);
    } catch (failure) {report(failure);}
    finally {listBusy.current = false;}
  }, [report, accountApi]);

  useEffect(() => {
    let active = true, socket, retryTimer, attempt = 0;
    function connect() {
      if (!active) return;
      socket = new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/accounts/live?account_id=${user.id}`, "chat.accounts.v1");
      socket.onopen = () => {attempt = 0; setLive(true);};
      socket.onmessage = () => {if (active) {refreshConversations(); setRevision(n => n + 1);}};
      socket.onclose = () => {
        if (!active) return;
        setLive(false);
        retryTimer = setTimeout(connect, Math.min(15000, 500 * 2 ** Math.min(attempt++, 5)) * (0.5 + Math.random() / 2));
      };
    }
    connect(); refreshConversations();
    const refresh = () => {refreshConversations(); setRevision(n => n + 1);};
    const interval = setInterval(refresh, 15000);
    window.addEventListener("focus", refresh);
    return () => {active = false; clearInterval(interval); clearTimeout(retryTimer); socket?.close(); window.removeEventListener("focus", refresh);};
  }, [refreshConversations, user.id]);

  useEffect(() => {
    if (!selected || historyMode) return;
    const controller = new AbortController();
    let active = true;
    setHistoryLoading(true);
    accountApi(`/conversations/${selected}/messages`, {signal: controller.signal}).then(data => {
      if (!active) return;
      setHistory(old => {
        let previous = old.id === selected ? old.items : [];
        // If many messages arrived while away, show a contiguous latest page.
        if (previous.length && data.items.length && data.items[0].seq > previous.at(-1).seq + 1) previous = [];
        const map = new Map(previous.map(item => [item.id, item]));
        for (const item of data.items) map.set(item.id, item);
        const items = [...map.values()].sort((a, b) => a.seq - b.seq).slice(-500);
        return {id: selected, items, before: items[0]?.seq > 1 ? items[0].seq : null};
      });
      if (data.items.length) setReadSeq(old => ({...old, [selected]: data.items.at(-1).seq}));
    }).catch(failure => {if (active && failure.name !== "AbortError") report(failure);})
      .finally(() => {if (active) setHistoryLoading(false);});
    return () => {active = false; controller.abort();};
  }, [selected, revision, report, historyMode, accountApi]);

  useEffect(() => {
    setResults([]);
    if (!/^[A-Za-z0-9_-]{2,32}$/.test(query)) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      accountApi("/users?q=" + encodeURIComponent(query), {signal: controller.signal})
        .then(data => setResults(data.items))
        .catch(failure => {if (failure.name !== "AbortError") report(failure);});
    }, 250);
    return () => {clearTimeout(timer); controller.abort();};
  }, [query, report, accountApi]);

  async function open(peer) {
    try {
      const data = await accountApi("/conversations", {method: "POST", body: JSON.stringify({user_id: peer.id})});
      if (!alive.current) return;
      setConversations(old => old.some(c => c.id === data.id) ? old : [{id: data.id, peer, last_seq: 0, updated_at: new Date().toISOString()}, ...old]);
      choose(data.id); setQuery("");
      refreshConversations();
    } catch (failure) {report(failure);}
  }
  async function send(event) {
    event?.preventDefault();
    const body = draft.replace(/\r\n?/g, "\n").replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, "");
    if (!selected || !body || sending.current) return;
    if ([...body].length > 2000) {setError("Messages can contain at most 2,000 characters."); return;}
    const id = selected, original = draft;
    let request = pending.current.get(id);
    if (!request || request.text !== body) request = {client_id: crypto.randomUUID(), text: body};
    pending.current.set(id, request);
    sending.current = true; setBusy(true); setError(""); setNotice("");
    try {
      await accountApi(`/conversations/${id}/messages`, {method: "POST", body: JSON.stringify(request)});
      if (!alive.current) return;
      pending.current.delete(id);
      setDrafts(old => old[id] === original ? {...old, [id]: ""} : old);
      setNotice("Saved to conversation history. Delivery and read status are not tracked yet.");
      setHistoryMode(false); followTail.current = true;
      setRevision(n => n + 1); refreshConversations();
    } catch (failure) {report(failure);}
    finally {sending.current = false; if (alive.current) setBusy(false);}
  }
  async function older() {
    const id = selected, before = history.before;
    setLoadingOlder(true); setHistoryMode(true);
    try {
      const data = await accountApi(`/conversations/${id}/messages?before=${before}`);
      if (!alive.current) return;
      setHistory(old => {
        if (old.id !== id) return old;
        const map = new Map([...data.items, ...old.items].map(item => [item.id, item]));
        // A bounded window can page arbitrarily far back; refresh returns to recent messages.
        const items = [...map.values()].sort((a, b) => a.seq - b.seq).slice(0, 500);
        return {id, items, before: data.next_before};
      });
    } catch (failure) {report(failure);}
    finally {if (alive.current) setLoadingOlder(false);}
  }
  async function moreConversations() {
    listCursor.current = next;
    await refreshConversations();
  }
  async function logout() {
    try {await accountApi("/auth/logout", {method: "POST", body: "{}"}); onLogout();}
    catch (failure) {report(failure);}
  }
  return <div className="app-shell saved-shell">
    <aside className="sidebar" aria-label="Saved conversations">
      <div className="sidebar-top"><a className="brand" href="/" aria-label="Baatchit"><span className="brand-mark"><Icon name="chat" /></span>baatchit.</a><span className="brand-caption">Your people. Your conversations.</span></div>
      <div className="sidebar-content">
        <label className="section-label" htmlFor="find-person">START A CONVERSATION</label>
        <input id="find-person" placeholder="Find a username…" value={query} onChange={e => setQuery(e.target.value)} autoComplete="off" maxLength={32} />
        <small>Type at least 2 characters.</small>
        <div className="account-results">{results.map(peer => <button className="peer" key={peer.id} onClick={() => open(peer)}><span className="peer-avatar">{peer.username.slice(0,2).toUpperCase()}</span><span>{peer.username}</span><span aria-hidden="true">＋</span></button>)}</div>
        <div className="sidebar-divider" /><div className="section-label">SAVED CHATS</div>
        <div className="peer-list">{conversations.map(c => <button key={c.id} className={"peer" + (selected === c.id ? " selected" : "")}
          aria-pressed={selected === c.id} onClick={() => choose(c.id)}>
          <span className="peer-avatar">{c.peer.username.slice(0,2).toUpperCase()}</span>
          <span className="room-copy"><strong>{c.peer.username}</strong><small>Saved conversation</small></span>
          {c.last_seq > (readSeq[c.id] || 0) && selected !== c.id && <span className="unread" aria-label="Activity since this tab opened">●</span>}
        </button>)}</div>
        {!conversations.length && <p className="sidebar-hint">Find someone by username to start your first saved chat.</p>}
        {next && <button className="quiet" onClick={moreConversations}>More conversations</button>}
      </div>
      <section className="profile"><div className="profile-heading"><span className="profile-avatar">{user.username.slice(0,2).toUpperCase()}</span><div><strong>{user.username}</strong><p>Signed-in account</p></div></div><button className="secondary" onClick={logout}>Sign out</button></section>
    </aside>
    <main className="chat">
      <header className="chat-header"><div className="header-room"><span className="header-room-icon"><Icon name="chat" /></span><div><div className="title-row"><h1>{current?.peer.username || "Your conversations"}</h1><span className="channel-tag">SAVED CHAT</span></div><p>{current ? "History stays available when you return" : "A familiar place to pick up where you left off"}</p></div></div><span role="status" className="status" data-connected={live}>{live ? "Live updates" : "Periodic refresh"}</span></header>
      <div className="saved-messages" ref={messageArea} onScroll={() => {
        const area = messageArea.current; followTail.current = area.scrollHeight - area.scrollTop - area.clientHeight < 100;
      }} aria-label="Saved message history" aria-busy={historyLoading}>
        {historyMode && <button className="secondary history-more" onClick={() => {setHistoryMode(false); followTail.current = true;}}>Return to latest messages</button>}
        {history.id === selected && history.before && <button className="secondary history-more" disabled={loadingOlder} onClick={older}>{loadingOlder ? "Loading…" : "Load older messages"}</button>}
        {!selected && <div className="saved-empty"><span className="welcome-icon"><Icon name="people" /></span><h2>Good conversations deserve a place to stay.</h2><p>Find a friend by username, or open a conversation from the sidebar.</p></div>}
        {selected && !shown.length && <div className="saved-empty"><h2>{historyLoading ? "Loading your history…" : "Say hello."}</h2><p>Your messages will be saved here, including when the other person is away.</p></div>}
        {shown.map(message => <article className={"saved-message" + (message.sender_id === user.id ? " own" : "")} key={message.id}>
          <div className="saved-message-meta"><strong>{message.sender_id === user.id ? "You" : current?.peer.username}</strong><time dateTime={message.sent_at}>{new Date(message.sent_at).toLocaleString()}</time></div><p>{message.text}</p>
        </article>)}
      </div>
      <footer className="composer-area"><div className="composer-inner">
        <p role="alert" className="account-error">{error}</p><p role="status" className="notice">{notice}</p>
        <form className="composer" onSubmit={send}><label className="sr-only" htmlFor="saved-message">Message {current?.peer.username || "conversation"}</label>
          <textarea id="saved-message" rows={2} disabled={!selected} value={draft} placeholder={selected ? "Write a message…" : "Choose a conversation to get started"}
            onChange={e => setDrafts(old => ({...old, [selected]: e.target.value}))}
            onKeyDown={e => {if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {e.preventDefault(); send();}}} />
          <button className="send" type="submit" disabled={!selected || !draft.trim() || busy}>{busy ? "Saving…" : "Send"}<Icon name="send" /></button></form>
        <div className="composer-meta"><span>Enter to send · Shift + Enter for a new line</span><span>{[...draft].length} / 2,000</span></div>
        <p className="privacy-note"><Icon name="info" /> Saved for conversation members. Messages are not end-to-end encrypted.</p>
      </div></footer>
    </main>
  </div>;
}
