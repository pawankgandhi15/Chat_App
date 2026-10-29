import {useMemo, useState} from "react";
import {Avatar, Brand, Button, SearchField, SkeletonList} from "../ui.jsx";
import {Icon} from "../Icon.jsx";

export function ConversationSidebar({user, chat}) {
  const [filter, setFilter] = useState("");
  const [activityOnly, setActivityOnly] = useState(false);
  const hasActivity = c => c.last_seq > (chat.readSeq[c.id] || 0) && chat.selected !== c.id;
  const visible = useMemo(() => chat.conversations.filter(c => c.peer.username.toLowerCase().includes(filter.toLowerCase())
    && (!activityOnly || (c.last_seq > (chat.readSeq[c.id] || 0) && chat.selected !== c.id))),
  [chat.conversations, filter, activityOnly, chat.readSeq, chat.selected]);
  const active = chat.conversations.filter(hasActivity).length;
  return <aside className="sidebar" aria-label="Saved conversations">
    <div className="sidebar-top"><Brand caption="Your people. Your conversations." /></div>
    <div className="sidebar-content">
      <div className="new-conversation-panel"><SearchField id="find-person" label="START A CONVERSATION" placeholder="Find a username…" value={chat.query} onChange={chat.setQuery} maxLength={32} help="Find a registered username. Type at least 2 characters." />
        <div className="account-results" aria-label="People search results" aria-busy={chat.searchState === "loading"}>
          {chat.searchState === "loading" && <SkeletonList label="Searching for people" count={1} />}
          {chat.results.map(peer => <Button variant="peer" key={peer.id} disabled={Boolean(chat.openingId)} busy={chat.openingId === peer.id} onClick={() => chat.open(peer)}>
            <Avatar name={peer.username} /><span className="room-copy"><strong>{peer.username}</strong><small>Start a saved chat</small></span><Icon name="plus" />
          </Button>)}
          {chat.searchState === "empty" && <p className="search-feedback" role="status">No accounts found. Check the username and try again.</p>}
          {chat.searchState === "error" && <p className="search-feedback" role="status">Search is unavailable. Try again in a moment.</p>}
        </div>
      </div>
      <div className="inbox-heading"><h2>Messages <span>{chat.conversations.length}</span></h2><Icon name="chat" /></div>
      <SearchField id="filter-chats" label="Filter loaded conversations" placeholder="Search your chats…" value={filter} onChange={setFilter} maxLength={32} />
      <div className="conversation-filters" role="group" aria-label="Conversation filters">
        <Button variant="filter-button" aria-pressed={!activityOnly} onClick={() => setActivityOnly(false)}>All chats</Button>
        <Button variant="filter-button" aria-pressed={activityOnly} onClick={() => setActivityOnly(true)}>Activity {active > 0 && <span>{active}</span>}</Button>
      </div>
      {chat.conversationsLoading && !chat.conversations.length && <SkeletonList />}
      <div className="peer-list" aria-label="Conversations">{visible.map(c => <Button key={c.id} variant="peer" className={chat.selected === c.id ? "selected" : ""} aria-pressed={chat.selected === c.id} onClick={() => chat.choose(c.id)}>
        <Avatar name={c.peer.username} /><span className="room-copy"><strong>{c.peer.username}</strong><small>{chat.drafts[c.id] ? <><span className="draft-label">Draft:</span> {chat.drafts[c.id]}</> : c.last_seq ? "Open conversation" : "Say hello"}</small></span>
        {hasActivity(c) && <span className="unread" aria-label="Activity since this tab opened">●</span>}
      </Button>)}</div>
      {chat.conversationsError && !chat.conversations.length ? <div className="search-feedback"><p role="alert">{chat.conversationsError}</p><Button onClick={chat.refreshConversations}>Retry conversations</Button></div>
        : !chat.conversationsLoading && !visible.length && <p className="search-feedback" role="status">{filter ? "No loaded chats match your search." : activityOnly ? "You're all caught up in this tab." : "Your conversations will appear here. Find someone above to get started."}</p>}
      {chat.next && <Button variant="quiet" onClick={chat.moreConversations}>More conversations</Button>}
      <p className="activity-help">Activity markers apply to this tab, not read receipts.</p>
    </div>
    <section className="profile"><div className="profile-heading"><Avatar name={user.username} className="profile-avatar" /><div><strong>{user.username}</strong><p>Signed-in account</p></div></div>
      <Button busy={chat.signingOut} onClick={chat.logout}><Icon name="logout" />{chat.signingOut ? "Signing out…" : "Sign out"}</Button>
    </section>
  </aside>;
}
