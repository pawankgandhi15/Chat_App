export const USERNAME = /^[A-Za-z0-9_-]{1,32}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const stamp = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/;
const encoder = new TextEncoder();
export function normalizeText(raw) {
  if (encoder.encode(raw).length > 16384) throw new Error("Message exceeds 16 KiB.");
  for (const c of raw) {
    const point = c.codePointAt(0);
    if (point >= 0xd800 && point <= 0xdfff) throw new Error("Message contains invalid Unicode.");
  }
  const text = raw.replace(/\r\n?/g, "\n").replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, "");
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(text)) throw new Error("Please remove unsupported control characters.");
  if ([...text].length > 2000) throw new Error("Keep messages within 2,000 characters.");
  return text;
}
export function parseEvent(raw) {
  if (typeof raw !== "string" || encoder.encode(raw).length > 65536) throw new Error("Invalid event.");
  const e = JSON.parse(raw);
  if (!e || Array.isArray(e) || e.schema_version !== 1) throw new Error("Unsupported protocol.");
  if (e.type === "peers") {
    if (Object.keys(e).length !== 3 || !Array.isArray(e.peers) || e.peers.length > 512) throw new Error("Invalid peer list.");
    const ids = new Set();
    for (const peer of e.peers) {
      if (!peer || Array.isArray(peer) || Object.keys(peer).length !== 2 ||
          typeof peer.connection_id !== "string" || !uuid.test(peer.connection_id) ||
          typeof peer.user !== "string" || !USERNAME.test(peer.user) || ids.has(peer.connection_id)) throw new Error("Invalid peer.");
      ids.add(peer.connection_id);
    }
    return e;
  }
  if (e.type === "notice") {
    if (Object.keys(e).length !== 4 || typeof e.client_id !== "string" || !uuid.test(e.client_id) ||
        typeof e.message !== "string" || e.message.length < 1 || e.message.length > 200) throw new Error("Invalid notice.");
    return e;
  }
  const fields = e.type === "session"
    ? ["schema_version", "type", "connection_id", "container_id", "user", "sent_at"]
    : ["schema_version", "type", "event_id", "sent_at", "user", "text", "container_id", "time",
       ...(e.type === "private" ? ["sender_id", "recipient_id", "recipient_user", "client_id"] : [])];
  if (Object.keys(e).length !== fields.length || fields.some(k => !Object.hasOwn(e, k))) throw new Error("Unexpected event fields.");
  if (typeof e.user !== "string" || !USERNAME.test(e.user) ||
      typeof e.container_id !== "string" || e.container_id.length < 1 || e.container_id.length > 64 ||
      typeof e.sent_at !== "string" || !stamp.test(e.sent_at) || !Number.isFinite(Date.parse(e.sent_at)) ||
      new Date(e.sent_at).toISOString() !== e.sent_at) throw new Error("Invalid event identity.");
  if (e.type === "session") {
    if (typeof e.connection_id !== "string" || !uuid.test(e.connection_id)) throw new Error("Invalid session.");
  } else if (!["chat", "system", "private"].includes(e.type) || typeof e.event_id !== "string" || !uuid.test(e.event_id) ||
      typeof e.text !== "string" || [...e.text].length < 1 || [...e.text].length > 2000 ||
      e.time !== e.sent_at.slice(11, 19) + " UTC") throw new Error("Invalid message.");
  if (e.type === "private" && (typeof e.sender_id !== "string" || !uuid.test(e.sender_id) ||
      typeof e.recipient_id !== "string" || !uuid.test(e.recipient_id) || e.sender_id === e.recipient_id ||
      typeof e.recipient_user !== "string" || !USERNAME.test(e.recipient_user) ||
      typeof e.client_id !== "string" || !uuid.test(e.client_id))) throw new Error("Invalid private message.");
  return e;
}
