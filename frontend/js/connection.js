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
    this.pendingTimer = null;
    this.socket = null;
  }
  clearTimers() {
    for (const name of ["timer", "stableTimer", "handshakeTimer", "pendingTimer"]) {
      if (this[name] !== null) this.clearTimer(this[name]);
      this[name] = null;
    }
  }
  stop() {
    this.generation++;
    this.clearTimers();
    if (this.socket) this.socket.close(1000);
    this.socket = null;
    this.store.update({connected: false, session: null, protocol: null, peers: [], pendingPrivate: null});
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
    const socket = new this.Socket(scheme + "//" + this.location.host + "/ws/" + encodeURIComponent(username), ["chat.v2", "chat.v1"]);
    this.socket = socket;
    let initialized = false;
    const current = () => generation === this.generation;
    this.handshakeTimer = this.setTimer(() => {
      if (current() && !initialized) socket.close(4000, "Session timeout");
    }, 10000);
    socket.onmessage = ({data}) => {
      if (!current()) return;
      try {
        if (!["chat.v1", "chat.v2"].includes(socket.protocol)) throw new Error("Unsupported protocol.");
        const event = parseEvent(data);
        if (!initialized) {
          if (event.type !== "session" || event.user !== username) throw new Error("Session must arrive first.");
          initialized = true;
          this.clearTimer(this.handshakeTimer);
          this.handshakeTimer = null;
          this.store.update({status: "Connected", connected: true, session: event, protocol: socket.protocol,
            notice: "You're connected. You can start chatting.", error: false});
          this.stableTimer = this.setTimer(() => { if (current()) this.attempt = 0; }, 30000);
        } else {
          if (event.type === "session") throw new Error("Unexpected second session.");
          if (event.type === "peers") {
            if (socket.protocol !== "chat.v2" || event.peers.some(peer => peer.connection_id === this.store.get().session.connection_id)) throw new Error("Invalid peer list.");
            this.store.update({peers: event.peers});
          } else if (event.type === "notice") {
            if (socket.protocol !== "chat.v2") throw new Error("Unexpected notice.");
            if (this.store.get().pendingPrivate?.id === event.client_id) {
              this.clearTimer(this.pendingTimer);
              this.pendingTimer = null;
              this.store.update({pendingPrivate: null, notice: event.message, error: true});
            }
          } else if (event.type === "private") {
            const own = this.store.get().session.connection_id;
            if (socket.protocol !== "chat.v2" || ![event.sender_id, event.recipient_id].includes(own)) throw new Error("Unexpected recipient.");
            const sent = event.sender_id === own;
            if (sent && this.store.get().pendingPrivate?.id === event.client_id) {
              this.clearTimer(this.pendingTimer);
              this.pendingTimer = null;
              this.store.confirmPrivate(event.client_id);
            }
            this.store.add({...event, from_self: sent, peer_id: sent ? event.recipient_id : event.sender_id,
              peer_user: sent ? event.recipient_user : event.user});
          } else this.store.add(event);
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
      this.store.update({connected: false, session: null, protocol: null, peers: [], pendingPrivate: null});
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
  send(raw, recipient = null) {
    const text = normalizeText(raw);
    if (!text) return false;
    if (!this.store.get().connected || this.socket?.readyState !== 1) throw new Error("Wait until connected to send.");
    if (this.store.get().pendingPrivate) throw new Error("Wait for the previous direct message to appear first.");
    if (this.socket.bufferedAmount > 65536) throw new Error("Connection is busy. Please wait before sending.");
    if (recipient && this.socket.protocol !== "chat.v2") throw new Error("Direct messages are unavailable on this server.");
    if (recipient && !this.store.get().peers.some(peer => peer.connection_id === recipient)) throw new Error("This person is offline. Your draft is kept here.");
    const clientId = recipient ? crypto.randomUUID() : null;
    const payload = this.socket.protocol === "chat.v2"
      ? JSON.stringify(recipient ? {type: "private", to: recipient, text, client_id: clientId} : {type: "chat", text}) : text;
    this.socket.send(payload);
    if (recipient) {
      this.store.update({pendingPrivate: {id: clientId, conversation: recipient, text: raw},
        notice: "Waiting for your message to appear. Your draft is kept until then.", error: false});
      this.pendingTimer = this.setTimer(() => {
        this.pendingTimer = null;
        if (this.store.get().pendingPrivate?.id === clientId) {
          this.store.update({pendingPrivate: null, notice: "Delivery is unconfirmed. Your draft is kept; resending may duplicate it.", error: true});
        }
      }, 8000);
    }
    return true;
  }
  disconnect() {
    this.stop();
    this.store.update({status: "Disconnected", notice: "Disconnected. Reconnect when you're ready.", error: false});
  }
}
