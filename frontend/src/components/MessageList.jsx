import {PureComponent, createRef, memo} from "react";
import {Icon} from "./Icon.jsx";

const Message = memo(function Message({event}) {
  if (event.type === "system") return <li className="system-message" data-id={event.event_id}>{event.text}</li>;
  return (
    <li className="message" data-id={event.event_id}>
      <span className="avatar" aria-hidden="true">{event.user.slice(0, 2).toUpperCase()}</span>
      <div className="message-content">
        <div className="message-heading"><strong>{event.user}</strong><time dateTime={event.sent_at}>{event.time}</time></div>
        <p>{event.text}</p>
      </div>
    </li>
  );
});

// Capture a retained visible message before React updates the bounded list.
export class MessageList extends PureComponent {
  scroller = createRef();
  list = createRef();
  state = {hasNewMessages: false};
  scrollRemainder = 0;

  getSnapshotBeforeUpdate(previousProps) {
    if (previousProps.messages === this.props.messages ||
        (previousProps.messages.length === this.props.messages.length &&
         previousProps.messages.every((event, index) => event === this.props.messages[index]))) return null;
    const scroller = this.scroller.current;
    const pinned = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 70;
    const top = scroller.getBoundingClientRect().top;
    const retained = new Set(this.props.messages.map(event => event.event_id));
    const anchor = [...this.list.current.children].find(node =>
      retained.has(node.dataset.id) && node.getBoundingClientRect().bottom > top);
    return {pinned, anchorId: anchor?.dataset.id, offset: anchor ? anchor.getBoundingClientRect().top - top : 0};
  }

  componentDidUpdate(previousProps, previousState, snapshot) {
    if (!snapshot) return;
    if (snapshot.pinned) {
      this.scrollToBottom();
    } else {
      const scroller = this.scroller.current;
      const anchor = [...this.list.current.children].find(node => node.dataset.id === snapshot.anchorId);
      if (anchor) {
        const target = scroller.scrollTop + anchor.getBoundingClientRect().top - scroller.getBoundingClientRect().top - snapshot.offset + this.scrollRemainder;
        scroller.scrollTop = target;
        // Preserve fractional pixels across repeated evictions; some browsers round scrollTop.
        this.scrollRemainder = target >= 0 && target <= scroller.scrollHeight - scroller.clientHeight
          ? target - scroller.scrollTop : 0;
      }
      if (!this.state.hasNewMessages) this.setState({hasNewMessages: true});
    }
  }

  scrollToBottom = () => {
    const scroller = this.scroller.current;
    scroller.scrollTop = scroller.scrollHeight;
    this.scrollRemainder = 0;
    if (this.state.hasNewMessages) this.setState({hasNewMessages: false});
  };

  onScroll = () => {
    const scroller = this.scroller.current;
    if (this.state.hasNewMessages && scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 70) {
      this.setState({hasNewMessages: false});
    }
  };

  render() {
    const hasChat = this.props.messages.some(event => event.type === "chat" || event.type === "private");
    const offline = ["Paused", "Disconnected", "Protocol error"].includes(this.props.status);
    return (
      <>
        <section className={hasChat ? "conversation" : "conversation conversation--empty"} aria-label="Conversation" ref={this.scroller} onScroll={this.onScroll}>
          {!hasChat && <div className="welcome">
            <div className="welcome-art" aria-hidden="true">
              <span className="art-orbit art-orbit-one" /><span className="art-orbit art-orbit-two" />
              <span className="art-bubble"><Icon name="chat" /></span>
              <span className="art-sparkle"><Icon name="sparkle" /></span>
              <span className="art-dot art-dot-one" /><span className="art-dot art-dot-two" />
            </div>
            <span className="welcome-eyebrow">{this.props.peer ? "A CONVERSATION FOR TWO" : "A LITTLE SPACE FOR EVERYONE"}</span>
            <h2>{this.props.peer ? <>Say hello to<br />{this.props.peer.user}<span>.</span></> : <>Good conversations<br />start here<span>.</span></>}</h2>
            <p>{this.props.peer ? <>Your conversation is between these two sessions.<br />Names are unverified and messages are temporary.</> : <>Say hello, share a thought, or just listen.<br />Everyone in this room can see your messages.</>}</p>
            <span className="welcome-status" data-connected={this.props.connected}>
              <span className="welcome-status-dot" />{this.props.connected ? "You're connected" : offline ? "You're offline" : "Waiting to connect"}
            </span>
          </div>}
          <ol id="messages" className="messages" role="log" aria-label="Live messages" aria-live="polite" aria-relevant="additions" tabIndex={0} ref={this.list}>
            {this.props.messages.map(event => <Message key={event.event_id} event={event} />)}
          </ol>
        </section>
        <button id="new-messages" className="new-messages" type="button" hidden={!this.state.hasNewMessages} onClick={this.scrollToBottom}>New messages ↓</button>
      </>
    );
  }
}
