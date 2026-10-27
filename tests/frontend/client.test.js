import test from "node:test";
import assert from "node:assert/strict";
import {normalizeText, parseEvent} from "../../frontend/js/protocol.js";
import {Connection} from "../../frontend/js/connection.js";
import {createStore} from "../../frontend/js/state.js";

const session = {schema_version:1, type:"session", connection_id:"5b2420aa-520f-4f0a-aea6-2a0d571098cf",
  container_id:"replica", user:"Alice", sent_at:"2026-10-27T10:00:00.000Z"};
test("normalization preserves Unicode and exact boundaries", () => {
  assert.equal(normalizeText(" \tA\r\nB\r "), "A\nB");
  assert.equal(normalizeText("\u00a0Ａ"), "\u00a0Ａ");
  assert.equal(normalizeText("😀".repeat(2000)).length, 4000);
  for (const value of ["a".repeat(2001), "\u0000", "\ud800"]) assert.throws(() => normalizeText(value));
});
test("strict event contract rejects added fields, invalid dates and wrong IDs", () => {
  assert.deepEqual(parseEvent(JSON.stringify(session)), session);
  for (const patch of [{extra:1}, {sent_at:"2026-02-30T10:00:00.000Z"}, {connection_id:"bad"}]) {
    assert.throws(() => parseEvent(JSON.stringify({...session, ...patch})));
  }
});
function harness() {
  const timers = new Map(); let seq = 0;
  class Socket {
    static instances = [];
    constructor() { this.protocol="chat.v1"; this.readyState=1; this.bufferedAmount=0; this.sent=[]; Socket.instances.push(this); }
    close() { this.readyState=3; }
    send(value) { this.sent.push(value); }
  }
  const store = createStore();
  const connection = new Connection(store, {Socket, location:{protocol:"http:",host:"localhost:8080"},
    random:()=>0.5, setTimer:(fn,ms)=>{timers.set(++seq,{fn,ms});return seq;}, clearTimer:id=>timers.delete(id)});
  return {store, connection, Socket, timers};
}
test("session gates sending; stale sockets cannot mutate replacement", () => {
  const {store, connection, Socket} = harness();
  connection.connect("Alice");
  assert.throws(() => connection.send("hi"));
  const first = Socket.instances[0];
  first.onmessage({data:JSON.stringify(session)});
  assert.equal(store.get().connected,true);
  assert.equal(connection.send(" hi "),true);
  assert.deepEqual(first.sent,["hi"]);
  store.update({draft:"unsent"});
  connection.connect("Alice");
  first.onmessage({data:"garbage"});
  assert.equal(store.get().status,"Connecting");
  assert.equal(store.get().draft,"unsent");
});
test("ten retries then pause, no replay of draft", () => {
  const {store, connection, Socket, timers} = harness();
  store.update({draft:"keep me"});
  connection.connect("Alice");
  for(let i=0;i<10;i++){
    Socket.instances.at(-1).onclose({code:1006});
    const pending=[...timers.values()][0]; timers.clear(); pending.fn();
  }
  Socket.instances.at(-1).onclose({code:1006});
  assert.equal(store.get().status,"Paused");
  assert.equal(store.get().draft,"keep me");
  assert.ok(Socket.instances.every(s=>s.sent.length===0));
});
test("out of order broadcast terminates protocol and cancels timers", () => {
  const {store, connection, Socket, timers} = harness();
  connection.connect("Alice");
  Socket.instances[0].onmessage({data:JSON.stringify({...session,type:"chat"})});
  assert.equal(store.get().status,"Protocol error");
  assert.equal(timers.size,0);
});
test("history remains bounded", () => {
  const store=createStore();
  for(let i=0;i<600;i++) store.add({event_id:String(i)});
  assert.equal(store.get().messages.length,500);
  assert.equal(store.get().messages[0].event_id,"100");
});
