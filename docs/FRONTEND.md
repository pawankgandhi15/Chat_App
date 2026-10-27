# React Frontend, UI/UX and Client Architecture

**Updated: 28 October 2026.** Baatchit uses React 19 and Vite 8 for its browser interface. This guide describes the implemented client. It supersedes the earlier native DOM renderer; the WebSocket protocol and backend architecture are unchanged.

## 1. Technology and build

| Layer | Implementation |
| --- | --- |
| Presentation | React and React DOM 19.3.1, JavaScript/JSX |
| Build and development | Vite 8.3.5, React plugin 6.1.2, Node.js 24 |
| Styling | Existing responsive CSS in `frontend/css/style.css` |
| Transport | Native browser WebSocket using `chat.v1` |
| Shared client logic | Framework-independent protocol parser, connection manager and memory store |
| Dependency management | Exact direct versions in `package.json` and integrity hashes in `package-lock.json` |
| Production serving | Vite emits `frontend/dist/`; an unprivileged Nginx container serves the output |

React adds component composition, controlled form fields and lifecycle cleanup. It also introduces a build step and a larger browser bundle. Dependencies are bundled into same-origin assets; the page does not load React from a third-party CDN. Node is used during development/build and is absent from the final Nginx runtime stage.

## 2. Component and module boundaries

~~~mermaid
flowchart TD
    Entry["main.jsx: React root and StrictMode"] --> App["App.jsx: interface composition"]
    App --> Hook["useChat: subscription, actions and lifecycle"]
    App --> Sidebar["Sidebar: editable display name"]
    App --> Header["ChatHeader: status and connection actions"]
    App --> Composer["Composer: draft, keyboard and send controls"]
    App --> Messages["MessageList: text rendering and scroll anchoring"]
    Hook --> Store["state.js: session, draft and bounded events"]
    Hook --> Connection["connection.js: sockets and retry timers"]
    Connection --> Parser["protocol.js: exact envelope and input rules"]
    Connection --> Store
    Store --> Hook
~~~

| Source | Responsibility and invariant |
| --- | --- |
| [main.jsx](../frontend/src/main.jsx) | Creates the React root, imports CSS and enables StrictMode for development lifecycle checks. |
| [App.jsx](../frontend/src/App.jsx) | Composes the sidebar, header, conversation and controlled composer. Retains semantic labels and stable IDs used by browser checks. |
| [useChat.js](../frontend/src/useChat.js) | Creates one retained store/connection pair per mounted app, subscribes to state, dispatches actions, and releases sockets/timers on cleanup. |
| [MessageList.jsx](../frontend/src/components/MessageList.jsx) | Renders strings as text, keys events by UUID and keeps the reading position stable when old messages are removed. |
| [connection.js](../frontend/js/connection.js) | Owns the native socket, generation token, session timeout and retry timers. Late events from obsolete sockets cannot mutate current state. |
| [protocol.js](../frontend/js/protocol.js) | Validates exact event fields, versions, identities and timestamps; normalizes outgoing plain text. |
| [state.js](../frontend/js/state.js) | Retains session status, draft and at most 500 events. Nothing is persisted to localStorage or a database. |
| [vite.config.js](../frontend/vite.config.js) | Defines loopback dev/preview servers, optional WebSocket proxy, CSP for production preview and static build output. |

The hook uses [React's `useSyncExternalStore`](https://react.dev/reference/react/useSyncExternalStore) to subscribe to the existing state module. Store snapshots retain object identity until an update. React does not maintain a second copy of the message history or transport state.

Most UI components are functions. The message list uses [`getSnapshotBeforeUpdate`](https://react.dev/reference/react/Component#getSnapshotBeforeUpdate) to measure a retained visible message before React changes the DOM. After the update, it restores that message's relative position. Fractional scroll rounding is carried forward to prevent drift over repeated evictions; native scroll anchoring is disabled for this container.

## 3. Connection lifecycle and message flow

1. The app creates a temporary name such as `guest_1234abcd`.
2. The effect connects to the current page host at `/ws/<encoded-name>`, using `ws:` for HTTP and `wss:` for HTTPS.
3. The socket requests `chat.v1`. The composer remains disabled until a valid first `session` event matches the requested name.
4. The user edits a controlled textarea. Enter submits, Shift+Enter adds a newline, and IME composition does not accidentally submit.
5. The client validates the draft and sends plain text. A successful `send()` clears the draft and shows an unconfirmed-delivery notice.
6. Broadcast events enter the store and render through React. The sender's event comes back through the backend/broker path; there is no separate optimistic echo.
7. Disconnecting disables the composer while preserving the draft and current in-memory history.

The display-name input has its own editable value. Submitting a valid name replaces the socket session, while the current draft remains in the store. An unsubmitted name edit does not silently change the connected identity.

The effect cleanup removes page listeners, stops the connection and cancels timers. This also handles StrictMode's development setup/cleanup cycle and hot refresh. Page hiding closes the socket; restoration from the browser's back/forward cache reconnects it. The connection's generation guard prevents old callbacks from updating a replacement session.

### Reconnect policy

| Condition | Behavior |
| --- | --- |
| Retryable close/network failure | Full jitter: random delay below `min(15,000 ms, 500 ms × 2^attempt)` |
| Server restart, code `1012` | Short jitter between 0 and 500 ms |
| Retry budget exhausted | Pause after ten attempts; expose manual Reconnect |
| Stable session | Reset retry count after 30 seconds |
| Codes `1000` / `1001` | Stop automatic retry; allow manual reconnect |
| Codes `1003` / `1007` / `1008` / `1009` | Stop retry and show policy/protocol guidance |
| Invalid or out-of-order event | Close the session, cancel timers and show Protocol error |

A missed broadcast is unrecoverable in the current ephemeral design. Draft retention means text remains in that tab; it is not automatically resent and does not survive a full page reload.

## 4. Input handling and safe rendering

- Usernames match `[A-Za-z0-9_-]{1,32}`. They are display labels, not authenticated identities.
- Raw outgoing input is limited to 16,384 UTF-8 bytes; invalid lone surrogates are rejected.
- CRLF and CR normalize to LF. Only boundary ASCII space, tab, CR and LF are trimmed; there is no NFC/NFKC normalization.
- Forbidden control characters are rejected. Tab and LF are allowed.
- Normalized text is limited to 2,000 Unicode code points. The character counter uses code points rather than JavaScript UTF-16 code units.
- Blank normalized input is not sent. Sending also requires a ready session and an acceptable browser transport buffer.
- Message bodies, names and system notices render as React text children. Never pass them through `dangerouslySetInnerHTML` or build HTML strings from received data.

Input validation and safe rendering have separate jobs: validation enforces the protocol; text rendering keeps HTML-like content inert. Future Markdown, links or attachments require a separate rendering/security design.

The gateway CSP permits same-origin scripts, styles, images and connections; it excludes inline scripts, third-party resources and embedding. Vite production preview applies the same policy. Development uses Vite's refresh client, so it is not a substitute for checking the built output. Favicon assets are emitted as files instead of `data:` URLs.

## 5. UI/UX and accessibility

| Area | Implemented behavior |
| --- | --- |
| Desktop | Sidebar with room/name information; conversation, status and composer in the main pane |
| Mobile | Compact top bar and stacked chat layout; checked at 390 × 844 pixels |
| Visual design | Dark surfaces, mint accent, existing CSS tokens and responsive breakpoints |
| Status | Connecting, Connected, Reconnecting, Paused, Disconnected and Protocol error states |
| Composer | Controlled draft, Unicode counter, disabled send before session or for blank text |
| Reading continuity | Follow the bottom when pinned; preserve the visible anchor while reading older messages |
| New-message action | Show a jump button when messages arrive while scrolled up |
| Memory bound | Remove old events beyond 500; retained events keep stable React keys |
| Accessibility basics | Semantic landmarks, explicit field labels, skip link, polite live status/log, visible keyboard focus |
| Motion | Respect reduced-motion preferences |

The current color tokens include `--bg: #101722`, `--line: #283241`, `--muted: #a1aec0`, `--text: #edf2f7` and `--accent: #a9e8cd`. CSS is the source of truth. The mobile browser check covers visibility and horizontal overflow; it is not a complete accessibility or cross-browser audit.

## 6. Local development and production delivery

Run from the repository root:

~~~bash
npm ci
npm run dev
~~~

Open **http://127.0.0.1:8080**. The dev server binds to loopback, supports hot refresh and fails when the chosen port is occupied. This starts only the frontend, so the chat remains disconnected without a backend. Windows PowerShell can use `npm.cmd` when execution policy blocks `npm.ps1`.

Optionally set `BAATCHIT_WS_TARGET=http://127.0.0.1:8000` before starting Vite to proxy `/ws` to an independently running backend. The backend needs Redis and must allow the exact browser Origin. This variable neither starts those services nor changes the production WebSocket URL.

~~~bash
npm run build
npm run preview
~~~

Stop the dev server before preview, or choose `npm run preview -- --port 8081`. Vite emits content-hashed files under `frontend/dist/assets/` and a generated HTML entry. The [Vite production build](https://vite.dev/guide/build) output can be served statically; raw JSX source cannot.

The Dockerfile runs `npm ci` and `npm run build` in a pinned Node 24 build stage, then copies only the generated output into the existing Nginx runtime stage. Kubernetes continues running the same frontend Deployment and Service. Nginx keeps HTML `no-store` and conservatively revalidates assets with `no-cache`.

CI installs locked npm dependencies, runs the client tests and builds the bundle before the existing full-stack checks. Changes to npm dependencies require a reviewed lockfile update. Never embed credentials in browser source or `VITE_*` variables.

## 7. Verification and remaining scope

- `npm test`: six existing protocol, normalization, socket-generation, retry and history-cap checks.
- `npm run build`: production JSX/module compilation and asset generation.
- `tests/browser/test_frontend.py`: three Chromium checks with intercepted WebSockets covering literal message content, Unicode counting, IME/keyboard handling, session gating, protocol failures, draft retention, rename, mobile layout, history eviction and scrolling.
- `tests/browser/test_ui.py`: the existing real two-tab backend/Redis browser flow, requiring the full stack.

The React checks run against both Vite development and production preview. Screenshots are generated under ignored `artifacts/react/`. Mocked WebSockets validate browser behavior only. The older 42-test and 7,500-delivery results remain dated baseline evidence; see [Implementation status](IMPLEMENTATION_STATUS.md) for verification boundaries.

There are still no accounts, rooms beyond the public general room, private conversations, durable history, receipts, typing indicators, media or end-to-end encryption. React changes the presentation/build layer; those features require additional product and backend work.
