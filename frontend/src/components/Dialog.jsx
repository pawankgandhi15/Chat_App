import {useEffect, useId, useRef} from "react";
import {createPortal} from "react-dom";
import {Button} from "./ui.jsx";
import {Icon} from "./Icon.jsx";

// Mount only while open. The native modal traps focus and makes the page inert.
export function Dialog({title, subtitle, onClose, children}) {
  const dialog = useRef(null);
  const titleId = useId();
  useEffect(() => {
    const node = dialog.current;
    const trigger = document.activeElement;
    node.showModal();
    return () => {node.close(); if (trigger?.isConnected) trigger.focus();};
  }, []);
  function keepFocus(event) {
    if (event.key !== "Tab") return;
    const controls = [...dialog.current.querySelectorAll("button, a[href], input, select, textarea, [tabindex]")]
      .filter(node => node.tabIndex >= 0 && !node.disabled && node.getClientRects().length && getComputedStyle(node).visibility !== "hidden");
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last.focus();}
    else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
  }
  return createPortal(<dialog ref={dialog} className="app-dialog" aria-labelledby={titleId}
    onKeyDown={keepFocus}
    onCancel={event => {event.preventDefault(); onClose();}}>
    <header className="dialog-heading"><div><h2 id={titleId}>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
      <Button variant="quiet" className="icon-button" aria-label={`Close ${title.toLowerCase()}`} onClick={onClose}><Icon name="close" /></Button>
    </header>
    {children}
  </dialog>, document.body);
}
