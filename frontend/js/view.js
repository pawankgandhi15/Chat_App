export function createView(doc = document) {
  const byId = id => doc.getElementById(id);
  const list = byId("messages"), scroller = doc.querySelector(".conversation");
  const newButton = byId("new-messages");
  let lastMessages = null;
  newButton.addEventListener("click", () => { scroller.scrollTop = scroller.scrollHeight; newButton.hidden = true; });
  scroller.addEventListener("scroll", () => {
    if (scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 70) newButton.hidden = true;
  });
  function messageNode(event) {
    const li = doc.createElement("li");
    li.dataset.id = event.event_id;
    if (event.type === "system") { li.className = "system-message"; li.textContent = event.text; return li; }
    li.className = "message";
    const avatar = doc.createElement("span");
    avatar.className = "avatar"; avatar.textContent = event.user.slice(0, 2).toUpperCase(); avatar.setAttribute("aria-hidden", "true");
    const content = doc.createElement("div"); content.className = "message-content";
    const heading = doc.createElement("div"); heading.className = "message-heading";
    const name = doc.createElement("strong"); name.textContent = event.user;
    const time = doc.createElement("time"); time.dateTime = event.sent_at; time.textContent = event.time;
    const text = doc.createElement("p"); text.textContent = event.text;
    heading.append(name, time); content.append(heading, text); li.append(avatar, content);
    return li;
  }
  return {
    bind({onDraft, onSend, onName, onReconnect, onDisconnect}) {
      byId("message").addEventListener("input", event => onDraft(event.target.value));
      byId("message-form").addEventListener("submit", event => { event.preventDefault(); onSend(); });
      byId("message").addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); onSend(); }
      });
      byId("profile-form").addEventListener("submit", event => { event.preventDefault(); onName(byId("username").value); });
      byId("reconnect").addEventListener("click", onReconnect);
      byId("disconnect").addEventListener("click", onDisconnect);
    },
    setName(name) { byId("username").value = name; },
    render(state) {
      byId("status").textContent = state.status; byId("status").dataset.connected = String(state.connected);
      byId("notice").textContent = state.notice; byId("notice").dataset.error = String(state.error);
      if (byId("message").value !== state.draft) byId("message").value = state.draft;
      byId("message").disabled = !state.connected;
      byId("send").disabled = !state.connected || !state.draft.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, "");
      byId("counter").textContent = [...state.draft].length.toLocaleString() + " / 2,000";
      byId("reconnect").hidden = !["Paused", "Disconnected", "Protocol error"].includes(state.status);
      byId("disconnect").hidden = byId("reconnect").hidden === false;
      if (lastMessages === state.messages) return;
      lastMessages = state.messages;
      const pinned = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 70;
      const ids = new Set(state.messages.map(e => e.event_id));
      for (const node of [...list.children]) {
        if (!ids.has(node.dataset.id)) {
          const height = node.getBoundingClientRect().height;
          node.remove();
          if (!pinned) scroller.scrollTop = Math.max(0, scroller.scrollTop - height);
        }
      }
      const existing = new Set([...list.children].map(n => n.dataset.id));
      const fragment = doc.createDocumentFragment();
      for (const event of state.messages) if (!existing.has(event.event_id)) fragment.append(messageNode(event));
      list.append(fragment);
      if (pinned) scroller.scrollTop = scroller.scrollHeight;
      else newButton.hidden = false;
    }
  };
}
