import {useEffect, useState, useSyncExternalStore} from "react";
import {Connection} from "../js/connection.js";
import {createStore} from "../js/state.js";

export function useChat() {
  const [{store, connection, initialUsername}] = useState(() => {
    const store = createStore();
    return {store, connection: new Connection(store),
      initialUsername: "guest_" + crypto.randomUUID().slice(0, 8)};
  });
  const state = useSyncExternalStore(store.subscribe, store.get);

  useEffect(() => {
    connection.connect(connection.username || initialUsername);
    const stop = () => connection.stop();
    const restore = event => {
      if (event.persisted) connection.connect(connection.username);
    };
    window.addEventListener("pagehide", stop);
    window.addEventListener("pageshow", restore);
    return () => {
      window.removeEventListener("pagehide", stop);
      window.removeEventListener("pageshow", restore);
      // StrictMode, hot refresh and unmount must release sockets and retry timers.
      connection.stop();
    };
  }, [connection, initialUsername]);

  const report = error => store.update({notice: error.message, error: true});
  function connect(username = connection.username) {
    try { connection.connect(username); } catch (error) { report(error); }
  }
  function send() {
    try {
      if (connection.send(store.get().draft)) {
        store.update({draft: "", notice: "Sent to the connection. Delivery is not confirmed until it appears in the room.", error: false});
      }
    } catch (error) { report(error); }
  }

  return {state, initialUsername, connect, send,
    setDraft: draft => store.update({draft}),
    disconnect: () => connection.disconnect()};
}
