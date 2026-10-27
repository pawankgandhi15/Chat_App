import {PureComponent, createRef, memo} from "react";

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
    if (previousProps.messages === this.props.messages) return null;
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
    return (
      <>
        <section className="conversation" aria-label="Conversation" ref={this.scroller} onScroll={this.onScroll}>
          <div className="welcome">
            <span className="welcome-symbol" aria-hidden="true">✳</span>
            <p className="eyebrow">THE START OF SOMETHING</p><h2>Pull up a chair.</h2>
            <p>Say hello, share a thought, or just listen.<br />Good conversations start with a simple message.</p>
            <div className="welcome-rule" />
          </div>
          <ol id="messages" className="messages" role="log" aria-label="Live messages" aria-live="polite" aria-relevant="additions" tabIndex={0} ref={this.list}>
            {this.props.messages.map(event => <Message key={event.event_id} event={event} />)}
          </ol>
        </section>
        <button id="new-messages" className="new-messages" type="button" hidden={!this.state.hasNewMessages} onClick={this.scrollToBottom}>New messages ↓</button>
      </>
    );
  }
}
