import {useSavedChat} from "./hooks/useSavedChat.js";
import {ConversationSidebar} from "./components/accounts/ConversationSidebar.jsx";
import {SavedHeader} from "./components/accounts/SavedHeader.jsx";
import {SavedTimeline} from "./components/accounts/SavedTimeline.jsx";
import {MessageComposer} from "./components/MessageComposer.jsx";
import {ConversationTools} from "./components/ConversationTools.jsx";

export function AccountChat({user, onLogout, onExpired}) {
  const chat = useSavedChat({user, onLogout, onExpired});
  return <>
    <a className="skip-link" href={chat.selected ? "#saved-message" : "#find-person"}>Skip to {chat.selected ? "message" : "people search"}</a>
    <div className="app-shell saved-shell">
      <ConversationSidebar user={user} chat={chat} />
      <main className="chat">
        <SavedHeader current={chat.current} live={chat.live} busy={chat.historyLoading} onRefresh={chat.refresh}>
          {chat.current && <ConversationTools key={chat.selected} name={chat.current.peer.username} saved direct connected={chat.live}
            messages={chat.shown.map(message => ({id: message.id, text: message.text, sentAt: message.sent_at, author: message.sender_id === user.id ? "You" : chat.current.peer.username}))} />}
        </SavedHeader>
        <SavedTimeline user={user} chat={chat} />
        <MessageComposer id="saved-message" label={`Message ${chat.current?.peer.username || "conversation"}`}
          placeholder={chat.selected ? "Write a message…" : "Choose a conversation to get started"}
          draft={chat.draft} onDraft={chat.setDraft} onSend={chat.send} disabled={!chat.selected}
          busy={chat.busy} busyLabel="Saving…" error={chat.error} notice={chat.notice}
          privacy="Saved for conversation members. Messages are not end-to-end encrypted." />
      </main>
    </div>
  </>;
}
