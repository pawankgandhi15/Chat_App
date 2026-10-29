const shortcuts = [
  ["Enter", "Send from the message composer when sending is available."],
  ["Shift + Enter", "Add a new line to your message."],
  ["Tab / Shift + Tab", "Move forward or backward between controls."],
  ["Escape", "Close this panel or the open emoji picker and return focus."],
];

export function KeyboardHelp() {
  return <section className="keyboard-help" aria-label="Keyboard help">
    <h3>Keep the conversation moving</h3><p>Use the keyboard to write, navigate and send.</p>
    <dl>{shortcuts.map(([keys, description]) => <div key={keys}><dt><kbd>{keys}</kbd></dt><dd>{description}</dd></div>)}</dl>
    <p className="details-note">Messages support up to 2,000 Unicode code points. Enter finishes an active input-method composition before it can send a message.</p>
  </section>;
}
