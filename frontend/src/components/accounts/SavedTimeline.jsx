import {Fragment, useEffect, useLayoutEffect, useRef, useState} from "react";
import {Button, EmptyState, Feedback, SkeletonList} from "../ui.jsx";
import {Icon} from "../Icon.jsx";

function dateLabel(value) {
  const date = new Date(value), today = new Date(), yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString(undefined, {month: "long", day: "numeric", year: "numeric"});
}

export function SavedTimeline({user, chat}) {
  const [away, setAway] = useState(false);
  const [copyNotice, setCopyNotice] = useState("");
  const copyTimer = useRef(null);
  const anchor = useRef(null);
  const mounted = useRef(true);
  useEffect(() => {mounted.current = true; return () => {mounted.current = false; clearTimeout(copyTimer.current);};}, []);
  useEffect(() => {setAway(false); setCopyNotice(""); anchor.current = null;}, [chat.selected]);
  useLayoutEffect(() => {
    if (!anchor.current) return;
    const area = chat.messageArea.current;
    const node = [...area.querySelectorAll("[data-message-id]")].find(el => el.dataset.messageId === anchor.current.id);
    if (node) area.scrollTop += node.getBoundingClientRect().top - area.getBoundingClientRect().top - anchor.current.offset;
    anchor.current = null;
  }, [chat.shown, chat.messageArea]);
  function older() {
    const area = chat.messageArea.current, top = area.getBoundingClientRect().top;
    const first = [...area.querySelectorAll("[data-message-id]")].find(el => el.getBoundingClientRect().bottom > top);
    anchor.current = first ? {id: first.dataset.messageId, offset: first.getBoundingClientRect().top - top} : null;
    chat.older();
  }
  async function copy(text) {
    let result;
    try {await navigator.clipboard.writeText(text); result = "Message copied to clipboard.";}
    catch {result = "Could not copy. You can select and copy the message text instead.";}
    if (!mounted.current) return;
    setCopyNotice(result); clearTimeout(copyTimer.current);
    copyTimer.current = setTimeout(() => setCopyNotice(""), 3000);
  }
  function jump() {
    if (chat.historyMode) chat.refresh();
    chat.followTail.current = true;
    chat.messageArea.current.scrollTop = chat.messageArea.current.scrollHeight;
    setAway(false);
  }
  return <section className="timeline-shell" aria-label="Conversation timeline">
    <div className="saved-messages" ref={chat.messageArea} tabIndex={0} onScroll={() => {
      const area = chat.messageArea.current;
      const pinned = area.scrollHeight - area.scrollTop - area.clientHeight < 100;
      chat.followTail.current = pinned; setAway(!pinned);
    }} aria-label="Saved message history" aria-busy={chat.historyLoading}>
      {chat.historyMode && <Button className="history-more" onClick={chat.refresh}>Return to latest messages</Button>}
      {chat.historyError && chat.shown.length > 0 && <div><Feedback id="history-error" error={chat.historyError} /><Button onClick={chat.refresh}>Retry message history</Button></div>}
      {chat.history.id === chat.selected && chat.history.before && <Button className="history-more" busy={chat.loadingOlder} onClick={older}>{chat.loadingOlder ? "Loading…" : "Load older messages"}</Button>}
      {!chat.selected && <EmptyState title="Every good conversation starts with hello." icon="people">Find someone by username, or choose a saved chat. Your next conversation is a message away.</EmptyState>}
      {chat.selected && !chat.shown.length && (chat.historyLoading ? <SkeletonList label="Loading your message history" /> : chat.historyError
        ? <EmptyState title="Let's try that again." icon="refresh" action={<Button onClick={chat.refresh}>Retry message history</Button>}>{chat.historyError} Please retry in a moment.</EmptyState>
        : <EmptyState title={`Say hello to ${chat.current?.peer.username || "your friend"}.`}>This is the beginning of your saved conversation. Messages stay here, even when one of you is away.</EmptyState>)}
      {chat.shown.map((message, index) => {
        const day = new Date(message.sent_at).toDateString();
        const newDay = index === 0 || day !== new Date(chat.shown[index - 1].sent_at).toDateString();
        const own = message.sender_id === user.id;
        return <Fragment key={message.id}>
          {newDay && <div className="date-divider"><span>{dateLabel(message.sent_at)}</span></div>}
          <article className={`saved-message${own ? " own" : ""}`} data-message-id={message.id}>
            <div className="saved-message-meta"><strong>{own ? "You" : chat.current?.peer.username}</strong><time dateTime={message.sent_at} title={new Date(message.sent_at).toLocaleString()}>{new Date(message.sent_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}</time>
              <Button variant="quiet" className="message-copy icon-button" aria-label={`Copy message ${message.seq}`} title="Copy message" onClick={() => copy(message.text)}><Icon name="copy" /></Button>
            </div><p>{message.text}</p>
          </article>
        </Fragment>;
      })}
    </div>
    {away && chat.selected && !chat.historyMode && <Button className="timeline-jump" onClick={jump}><Icon name="arrowDown" />Jump to latest</Button>}
    <span className="copy-notice" role="status">{copyNotice}</span>
  </section>;
}
