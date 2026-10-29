import {useState} from "react";
import {Button} from "./ui.jsx";
import {Icon} from "./Icon.jsx";
import {Dialog} from "./Dialog.jsx";
import {MessageSearch} from "./MessageSearch.jsx";
import {ConversationDetails} from "./ConversationDetails.jsx";
import {KeyboardHelp} from "./KeyboardHelp.jsx";

export function ConversationTools({name, messages, saved = false, direct = false, connected}) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState("search");
  return <>
    <Button variant="quiet" className="icon-button conversation-tools-trigger" aria-label="Conversation tools" title="Search, details and keyboard help"
      aria-haspopup="dialog" onClick={() => {setView("search"); setOpen(true);}}><Icon name="search" /></Button>
    {open && <Dialog title="Conversation tools" subtitle={name} onClose={() => setOpen(false)}>
      <nav className="tools-navigation" aria-label="Conversation tools sections">
        {[["search", "Search", "search"], ["details", "Details", "info"], ["keyboard", "Keyboard", "keyboard"]].map(([key, label, icon]) =>
          <Button key={key} variant="quiet" aria-pressed={view === key} onClick={() => setView(key)}><Icon name={icon} />{label}</Button>)}
      </nav>
      <div className="tools-content">
        <div hidden={view !== "search"}><MessageSearch messages={messages} saved={saved} /></div>
        {view === "details" && <ConversationDetails name={name} saved={saved} direct={direct} connected={connected} messageCount={messages.length} />}
        {view === "keyboard" && <KeyboardHelp />}
      </div>
    </Dialog>}
  </>;
}
