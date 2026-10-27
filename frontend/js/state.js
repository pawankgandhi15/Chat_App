export function createStore() {
  let state = {status: "Connecting", connected: false, session: null, messages: [],
    draft: "", notice: "Waiting for a session…", error: false};
  const listeners = new Set();
  return {
    get: () => state,
    update(patch) { state = {...state, ...patch}; listeners.forEach(fn => fn(state)); },
    add(event) { state = {...state, messages: [...state.messages, event].slice(-500)}; listeners.forEach(fn => fn(state)); },
    subscribe(fn) { listeners.add(fn); fn(state); return () => listeners.delete(fn); }
  };
}
