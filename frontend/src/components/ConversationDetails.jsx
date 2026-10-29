import {Avatar} from "./ui.jsx";

export function ConversationDetails({name, saved, direct, connected, messageCount}) {
  return <section className="conversation-details" aria-label="Conversation details">
    <div className="details-identity"><Avatar name={name} /><div><h3>{name}</h3><p>{saved ? "Saved direct conversation" : direct ? "Guest direct conversation" : "Public guest room"}</p></div></div>
    <dl className="details-facts">
      <div><dt>Audience</dt><dd>{saved ? "You and the other account" : direct ? "These two guest sessions" : "Everyone connected to General"}</dd></div>
      <div><dt>History</dt><dd>{saved ? "Saved on the server; older pages can be loaded in the timeline." : "Temporary in this tab; no replay after reconnecting."}</dd></div>
      <div><dt>Identity</dt><dd>{saved ? "Signed-in accounts with stable IDs" : "Display names are unverified"}</dd></div>
      <div><dt>{saved ? "Updates" : "Connection"}</dt><dd>{saved ? (connected ? "Live update hints connected" : "Periodic refresh; live updates unavailable") : connected ? "Connected" : "Not connected"}</dd></div>
      <div><dt>Loaded messages</dt><dd>{messageCount} in the current view</dd></div>
    </dl>
    <p className="details-note">Messages are not end-to-end encrypted.{saved && " Live-update status does not show whether the other person is online. Read receipts are not available."}</p>
  </section>;
}
