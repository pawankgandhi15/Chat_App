import {Connection} from "./connection.js";
import {createStore} from "./state.js";
import {createView} from "./view.js";
const store = createStore();
const view = createView();
const connection = new Connection(store);
let username = "guest_" + crypto.randomUUID().slice(0, 8);
view.setName(username);
store.subscribe(state => view.render(state));
const report = error => store.update({notice: error.message, error: true});
function connect(name) {
  try { connection.connect(name); username = name; } catch (error) { report(error); }
}
view.bind({
  onDraft: draft => store.update({draft}),
  onSend: () => {
    try {
      if (connection.send(store.get().draft)) store.update({draft: "", notice: "Sent to the connection. Delivery is not confirmed until it appears in the room.", error: false});
    } catch (error) { report(error); }
  },
  onName: connect, onReconnect: () => connect(username), onDisconnect: () => connection.disconnect()
});
window.addEventListener("pagehide", () => connection.stop());
connect(username);
