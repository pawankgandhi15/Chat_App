import {useId, useState} from "react";
import {SearchField} from "./ui.jsx";

export function MessageSearch({messages, saved}) {
  const [query, setQuery] = useState("");
  const id = useId();
  const term = query.trim().toLocaleLowerCase();
  const matches = term ? messages.filter(message => message.text.toLocaleLowerCase().includes(term)) : [];
  return <section className="message-search" aria-label="Message search">
    <SearchField id={id} label="Search loaded messages" value={query} onChange={setQuery}
      placeholder="Find a word or phrase…" maxLength={200}
      help={saved ? "Searches this conversation's loaded history only. Load older messages in the timeline to search more." : "Searches messages still in this tab for the selected conversation. Guest messages are temporary."} />
    <p className="tools-caption" role="status">{!term ? `${messages.length} messages available to search.` : matches.length ? `${matches.length} matching messages${matches.length > 50 ? " · showing the latest 50" : ""}.` : "No matches in loaded messages. Try another phrase."}</p>
    <ol className="search-results" aria-label="Matching messages">
      {matches.slice(-50).reverse().map(message => <li key={message.id}>
        <div><strong>{message.author}</strong><time dateTime={message.sentAt}>{new Date(message.sentAt).toLocaleString()}</time></div>
        <p>{message.text}</p>
      </li>)}
    </ol>
  </section>;
}
