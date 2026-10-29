import {useCallback, useEffect, useRef, useState} from "react";
import {api} from "../services/api.js";

export function useSavedChat({user, onLogout, onExpired}) {
  const accountApi = useCallback((path, options = {}) => api(path, {...options,
    headers: {...options.headers, "X-Account-ID": user.id}}), [user.id]);
  const [conversations, setConversations] = useState([]);
  const [next, setNext] = useState(null);
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState({id: null, items: [], before: null});
  const [drafts, setDrafts] = useState({});
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searchState, setSearchState] = useState("idle");
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [conversationsError, setConversationsError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [openingId, setOpeningId] = useState(null);
  const [signingOut, setSigningOut] = useState(false);
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
  const opening = useRef(false);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
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
    if (failure.status === 401) onExpired(failure.message);
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
      setConversationsError("");
    } catch (failure) {if (alive.current) setConversationsError("Your conversations couldn't be loaded."); if (failure.status === 401) report(failure);}
    finally {listBusy.current = false; if (alive.current) setConversationsLoading(false);}
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
    setHistoryError("");
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
    }).catch(failure => {if (active && failure.name !== "AbortError") {setHistoryError("Your message history couldn't be loaded."); if (failure.status === 401) report(failure);}})
      .finally(() => {if (active) setHistoryLoading(false);});
    return () => {active = false; controller.abort();};
  }, [selected, revision, report, historyMode, accountApi]);

  useEffect(() => {
    setResults([]);
    if (!/^[A-Za-z0-9_-]{2,32}$/.test(query)) {setSearchState("idle"); return;}
    const controller = new AbortController();
    let active = true;
    setSearchState("loading");
    const timer = setTimeout(() => {
      accountApi("/users?q=" + encodeURIComponent(query), {signal: controller.signal})
        .then(data => {if (active) {setResults(data.items); setSearchState(data.items.length ? "ready" : "empty");}})
        .catch(failure => {if (active && failure.name !== "AbortError") {setSearchState("error"); if (failure.status === 401) report(failure);}});
    }, 250);
    return () => {active = false; clearTimeout(timer); controller.abort();};
  }, [query, report, accountApi]);

  async function open(peer) {
    if (opening.current) return;
    opening.current = true; setOpeningId(peer.id);
    try {
      const data = await accountApi("/conversations", {method: "POST", body: JSON.stringify({user_id: peer.id})});
      if (!alive.current) return;
      setConversations(old => old.some(c => c.id === data.id) ? old : [{id: data.id, peer, last_seq: 0, updated_at: new Date().toISOString()}, ...old]);
      choose(data.id); setQuery("");
      refreshConversations();
    } catch (failure) {report(failure);}
    finally {opening.current = false; if (alive.current) setOpeningId(null);}
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
      if (selectedRef.current === id) {
        setNotice("Saved to conversation history. Delivery and read status are not tracked yet.");
        setHistoryMode(false); followTail.current = true;
      }
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
    setSigningOut(true);
    try {await accountApi("/auth/logout", {method: "POST", body: "{}"}); onLogout();}
    catch (failure) {report(failure);}
    finally {if (alive.current) setSigningOut(false);}
  }
  return {conversations, next, selected, history, drafts, query, results, error, notice, busy,
    loadingOlder, historyLoading, historyMode, live, readSeq, current, shown, draft,
    searchState, conversationsLoading, conversationsError, historyError, openingId, signingOut,
    messageArea, followTail, choose, open, send, older, moreConversations, logout,
    setQuery, setDraft: value => setDrafts(old => ({...old, [selected]: value})),
    refresh: () => {setHistoryMode(false); followTail.current = true; setRevision(n => n + 1);},
    refreshConversations};
}
