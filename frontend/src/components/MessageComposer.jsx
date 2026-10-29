import {useRef} from "react";
import {Icon} from "./Icon.jsx";
import {Button, Feedback} from "./ui.jsx";

const EMOJI = ["😊", "👋", "❤️", "👍", "🎉", "😂", "🙏", "✨"];

export function MessageComposer({id = "message", label, placeholder, draft, onDraft, onSend, disabled = false,
  busy = false, busyLabel = "Send", error = "", notice = "", privacy}) {
  const input = useRef(null);
  const picker = useRef(null);
  const count = [...draft].length;
  const tooLong = count > 2000;
  const canSend = !disabled && !busy && !tooLong && Boolean(draft.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, ""));
  function submit(event) {
    event.preventDefault();
    if (canSend) onSend();
  }
  function insertEmoji(emoji) {
    const start = input.current.selectionStart, end = input.current.selectionEnd;
    onDraft(draft.slice(0, start) + emoji + draft.slice(end));
    picker.current.open = false;
    requestAnimationFrame(() => {input.current?.focus(); input.current?.setSelectionRange(start + emoji.length, start + emoji.length);});
  }
  return <footer className="composer-area"><div className="composer-inner">
    <Feedback id="notice" error={error || (tooLong ? "Your message is too long. Keep it within 2,000 characters." : "")} notice={notice} />
    <form id="message-form" className="composer" onSubmit={submit}>
      <label className="sr-only" htmlFor={id}>{label}</label>
      <textarea ref={input} id={id} rows={2} placeholder={placeholder} disabled={disabled} value={draft}
        aria-invalid={tooLong || undefined} aria-describedby="composer-help counter" onChange={e => onDraft(e.target.value)}
        onKeyDown={e => {if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) submit(e);}} />
      <div className="composer-actions">
        {!disabled && <details className="emoji-picker" ref={picker}
          onBlur={e => {if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false;}}
          onKeyDown={e => {if (e.key === "Escape") {e.preventDefault(); picker.current.open = false; picker.current.querySelector("summary").focus();}}}>
          <summary aria-label="Add emoji" title="Add emoji"><Icon name="smile" /></summary>
          <div className="emoji-options" role="group" aria-label="Choose an emoji">{EMOJI.map(emoji => <button type="button" key={emoji} aria-label={`Insert ${emoji}`} onClick={() => insertEmoji(emoji)}>{emoji}</button>)}</div>
        </details>}
        <Button id="send" variant="send" type="submit" disabled={!canSend} busy={busy}><span>{busy ? busyLabel : "Send"}</span>{!busy && <Icon name="send" />}</Button>
      </div>
    </form>
    <div className="composer-meta"><span id="composer-help"><kbd>Enter</kbd> to send · <kbd>Shift + Enter</kbd> for a new line</span><span id="counter" data-invalid={tooLong}>{count.toLocaleString()} / 2,000</span></div>
    <p className="privacy-note"><Icon name="info" />{privacy}</p>
  </div></footer>;
}
