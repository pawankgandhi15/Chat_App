import {parseEvent, normalizeText, USERNAME} from "./protocol.js";

export class Connection {
  constructor(store, {Socket = globalThis.WebSocket, random = Math.random,
    setTimer = (fn, ms) => globalThis.setTimeout(fn, ms),
    clearTimer = id => globalThis.clearTimeout(id), location = globalThis.location} = {}) {
    Object.assign(this, {store, Socket, random, setTimer, clearTimer, location});
    this.generation = 0;
    this.attempt = 0;
    this.timer = null;
    this.stableTimer = null;
    this.handshakeTimer = null;
    this.socket = null;
  }
  clearTimers() {
    for (const name of ["timer", "stableTimer", "handshakeTimer"]) {
      if (this[name] !== null) this.clearTimer(this[name]);
      this[name] = null;
    }
  }
  stop() {
    this.generation++;
    this.clearTimers();
    if (this.socket) this.socket.close(1000);
    this.socket = null;
    this.store.update({connected: false, session: null});
  }
  connect(username, reset = true) {
    if (!USERNAME.test(username)) throw new Error("Use 1–32 letters, numbers, underscores or hyphens.");
    this.stop();
    this.username = username;
    if (reset) this.attempt = 0;
    const generation = this.generation;
    this.store.update({status: this.attempt ? "Reconnecting (" + this.attempt + "/10)" : "Connecting",
      notice: "Connecting… Your draft is kept here.", error: false});
    const scheme = this.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new this.Socket(scheme + "//" + this.location.host + "/ws/" + encodeURIComponent(username), ["chat.v1"]);
    this.socket = socket;
    let initialized = false;
    const current = () => generation === this.generation;
    this.handshakeTimer = this.setTimer(() => {
      if (current() && !initialized) socket.close(4000, "Session timeout");
    }, 10000);
    socket.onmessage = ({data}) => {
      if (!current()) return;
      try {
        if (socket.protocol !== "chat.v1") throw new Error("Unsupported protocol.");
        const event = parseEvent(data);
        if (!initialized) {
          if (event.type !== "session" || event.user !== username) throw new Error("Session must arrive first.");
          initialized = true;
          this.clearTimer(this.handshakeTimer);
          this.handshakeTimer = null;
          this.store.update({status: "Connected", connected: true, session: event,
            notice: "You're connected. Say hello to the room.", error: false});
          this.stableTimer = this.setTimer(() => { if (current()) this.attempt = 0; }, 30000);
        } else {
          if (event.type === "session") throw new Error("Unexpected second session.");
          this.store.add(event);
        }
      } catch {
        this.stop();
        this.store.update({status: "Protocol error", notice: "The server sent an incompatible event. Reconnect to try again.", error: true});
      }
    };
    socket.onerror = () => {};
    socket.onclose = ({code}) => {
      if (!current()) return;
      this.clearTimers();
      this.store.update({connected: false, session: null});
      if ([1000, 1001, 1003, 1007, 1008, 1009].includes(code)) {
        this.store.update({status: code < 1003 ? "Disconnected" : "Protocol error",
          notice: code < 1003 ? "Disconnected. Reconnect when you're ready." : "Connection closed by message policy. Check your input before reconnecting.",
          error: code >= 1003});
        return;
      }
      if (this.attempt >= 10) {
        this.store.update({status: "Paused", notice: "Couldn't reconnect. Your draft is safe here; try again manually.", error: true});
        return;
      }
      const delay = this.random() * (code === 1012 ? 500 : Math.min(15000, 500 * 2 ** this.attempt));
      this.attempt++;
      this.store.update({status: "Reconnecting (" + this.attempt + "/10)",
        notice: "Connection interrupted. Missed messages cannot be recovered. Your draft is kept here."});
      this.timer = this.setTimer(() => { if (current()) this.connect(username, false); }, delay);
    };
  }
  send(raw) {
    const text = normalizeText(raw);
    if (!text) return false;
    if (!this.store.get().connected || this.socket?.readyState !== 1) throw new Error("Wait until connected to send.");
    if (this.socket.bufferedAmount > 65536) throw new Error("Connection is busy. Please wait before sending.");
    this.socket.send(text);
    return true;
  }
  disconnect() {
    this.stop();
    this.store.update({status: "Disconnected", notice: "Disconnected. Reconnect when you're ready.", error: false});
  }
}
