import {Avatar, Button, StatusBadge} from "../ui.jsx";
import {Icon} from "../Icon.jsx";

export function SavedHeader({current, live, onRefresh, busy, children}) {
  return <header className="chat-header"><div className="header-room">
    {current ? <Avatar name={current.peer.username} className="header-room-icon" /> : <span className="header-room-icon"><Icon name="chat" /></span>}
    <div><div className="title-row"><h1>{current?.peer.username || "Your conversations"}</h1><span className="channel-tag">SAVED CHAT</span></div><p>{current ? "Just the two of you. History stays here." : "Pick up where you left off"}</p></div>
  </div><div className="connection-controls"><StatusBadge connected={live}>{live ? "Live updates" : "Periodic refresh"}</StatusBadge>
    {current && <Button variant="quiet" className="icon-button" aria-label="Refresh conversation" title="Refresh conversation" disabled={busy} onClick={onRefresh}><Icon name="refresh" /></Button>}
    {children}
  </div></header>;
}
