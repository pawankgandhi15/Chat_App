export function createStore() {
  let state = {status: "Connecting", connected: false, session: null, protocol: null, messages: [],
    draft: "", drafts: {}, conversation: "general", knownPeers: {}, peers: [], unread: {}, pendingPrivate: null,
    notice: "Waiting for a session…", error: false};
  const listeners = new Set();
  return {
    get: () => state,
    update(patch) { state = {...state, ...patch}; listeners.forEach(fn => fn(state)); },
    add(event) {
      const messages = [...state.messages, event].slice(-500);
      const unread = {...state.unread};
      if (event.type === "private" && event.peer_id !== state.conversation && !event.from_self) {
        unread[event.peer_id] = Math.min(999, (unread[event.peer_id] || 0) + 1);
      }
      const retained = new Set(messages.map(message => message.peer_id).filter(Boolean));
      for (const id of Object.keys(unread)) if (!retained.has(id)) delete unread[id];
      state = {...state, messages, unread}; listeners.forEach(fn => fn(state));
    },
    select(id) {
      if (id === state.conversation) return;
      const drafts = {...state.drafts};
      if (state.draft) drafts[state.conversation] = state.draft;
      else delete drafts[state.conversation];
      const known = {...state.knownPeers};
      const peer = state.peers.find(item => item.connection_id === id);
      if (peer) known[id] = peer.user;
      const needed = new Set([...Object.keys(drafts), id, ...state.messages.map(event => event.peer_id).filter(Boolean)]);
      for (const key of Object.keys(known)) if (!needed.has(key)) delete known[key];
      const unread = {...state.unread};
      delete unread[id];
      state = {...state, drafts, knownPeers: known, unread, conversation: id, draft: drafts[id] || ""};
      listeners.forEach(fn => fn(state));
    },
    confirmPrivate(id) {
      const pending = state.pendingPrivate;
      if (!pending || pending.id !== id) return;
      const drafts = {...state.drafts};
      let draft = state.draft;
      if (state.conversation === pending.conversation) {
        if (draft === pending.text) draft = "";
      } else if (drafts[pending.conversation] === pending.text) delete drafts[pending.conversation];
      state = {...state, draft, drafts, pendingPrivate: null,
        notice: "Your direct message appeared in its conversation. Delivery to the other person is not confirmed.", error: false};
      listeners.forEach(fn => fn(state));
    },
    subscribe(fn) { listeners.add(fn); fn(state); return () => listeners.delete(fn); }
  };
}
