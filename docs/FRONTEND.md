# Frontend Technology and UI/UX Guide

**Status:** Specification for future implementation; no frontend has been built or tested. Created 2026-10-26.

This guide brings together the browser technology, screen design, interaction rules, accessibility, security, integration and delivery requirements for the anonymous global chat. Read it with the [backend guide](BACKEND.md). Existing protocol and configuration contracts remain owned by their linked specifications; the visual choices below are proposed design defaults.

## 1. Product Experience and Scope

The visitor opens the site, receives a temporary display name, connects to the global chat and exchanges text messages. The interface should make connection state and message-loss limitations understandable without exposing infrastructure details in the main conversation.

The baseline has one screen and one global conversation. Accounts, room switching, attachments, typing indicators, read receipts, durable history and an authoritative online-user count require additional backend contracts and are deferred. Display names are labels rather than verified identities, and two visitors can have the same name.

## 2. Technology and Tooling

| Technology | Responsibility | Project decision |
| --- | --- | --- |
| Semantic HTML | Page structure, controls and accessible labels | Static `index.html` with external assets. |
| CSS | Layout, themes, responsive behavior and focus states | Custom properties, Flexbox/Grid and media queries; no UI framework required. |
| Native JavaScript | UI state, validation, DOM rendering and connection lifecycle | Browser modules with a small explicit state object. |
| Browser WebSocket API | Persistent connection and event transport | Same-origin `/ws/{username}` using `chat.v1`. |
| Browser URL, encoding and date APIs | Safe endpoint construction, UTF-8 size checks and timestamp presentation | Use platform functionality rather than adding dependencies for these tasks. |
| Nginx static server | Deliver HTML, CSS and JavaScript | Frontend container behind the separate gateway. |
| OCI images / Kubernetes | Reproducible serving and integration | Frontend has a ClusterIP Service; only the gateway is public. Local testing uses k3d. |
| Browser automation and accessibility tooling | Verify behavior across browsers and assistive technology | Select and pin a runner at implementation; Playwright and axe-core are candidate development tools. |

The baseline needs no Node.js runtime, React, backend template rendering, CDN scripts or client secrets. A future test toolchain can have development dependencies without adding them to the shipped frontend. Review actual dependency/image versions and browser support when implementing; the version table in [technologies](TECHNOLOGIES.md) is design input, not evidence of a tested lockfile.

## 3. Screen Layout and Information Hierarchy

```text
+----------------------------------------------------------+
| Chat App          Global chat       Theme    Disconnect  |
| Display name: Guest_a92f     [Connected]                  |
+----------------------------------------------------------+
| Live conversation                                        |
|   System: Welcome. Messages are not saved.                |
|   Guest_b17c  14:32    Hello!                              |
|   Guest_a92f  14:33    Hi there.                           |
|                                                          |
|                                  [New messages below]    |
+----------------------------------------------------------+
| Connection notice or validation feedback, when needed     |
| Message                                                  |
| [Write a message...                              ]        |
| 0 / 2000       Enter to send; Shift+Enter newline   [Send] |
+----------------------------------------------------------+
```

| Region | Required content and behavior |
| --- | --- |
| Header | Product name, global-channel label, display name and optional theme control; show the current state in text. |
| Connection notice | Concise status and recovery action; visible near the composer during failure. |
| Conversation | Chronological chat entries and visually distinct system notices; meaningful empty state. |
| Message entry | Sender label, body and time. Keep body text selectable and preserve allowed newlines. |
| Composer | Explicit textarea label, counter, send button and keyboard help. |
| New-message control | Appears when messages arrive while the visitor is reading older entries; activates scroll to the latest entry. |
| Optional diagnostics | Collapsed development/demo details such as serving replica and release; avoid making them part of every public message. |

Do not label a message as authenticated, delivered to everyone or read. The event schema also lacks a per-message sender connection ID: matching a display name is insufficient to reliably mark an entry as “You.” Use neutral sender labels unless the protocol is intentionally extended.

## 4. Proposed Visual Design System

| Property | Proposed starting value | Review requirement |
| --- | --- | --- |
| Typography | System font stack, 16 px body, approximately 1.5 line height | Readable under browser zoom and platform text scaling. |
| Spacing | 4, 8, 12, 16, 24 and 32 px scale | Consistent padding around entries, controls and notices. |
| Content width | Approximately 960 px maximum on desktop | Center the chat; use available width on small screens. |
| Control height | Aim for at least 44 px for primary touch controls | Include sufficient spacing between independent targets. |
| Corners | 8 px controls, 12 px main panels | Keep a restrained, consistent treatment. |
| Colors | Tokens for canvas, surface, text, muted text, border, accent, success, warning and danger | Define separate light/dark values; test contrast before acceptance. |
| Focus | Clearly visible outline with offset | Never remove keyboard focus without an equivalent indicator. |
| Motion | Short, subtle state changes | Respect reduced-motion preferences and avoid flashing effects. |

Use system light/dark preference initially. A theme toggle is optional; its accessible name must describe the action or current selection. Persisting only a theme preference may be added explicitly, while conversation text and drafts remain memory-only in the baseline.

Candidate CSS tokens include `--color-canvas`, `--color-surface`, `--color-text`, `--color-muted`, `--color-accent`, `--color-danger`, `--space-4`, `--radius-control` and `--content-width`. These are names to implement later, not existing CSS variables.

## 5. Responsive and Accessible Behavior

- At narrow widths, stack header actions, let entries wrap and keep the composer usable without horizontal page scrolling. Test at 320 CSS px and at browser zoom.
- Use a flexible conversation region and a composer within the page layout. Account for mobile browser chrome, safe-area insets and the on-screen keyboard; avoid an overlay that covers recent messages or input.
- Break long URLs and unbroken text visually without mutating message content. Use isolated text direction for user-provided names and bodies to protect surrounding UI layout.
- Provide semantic landmarks, a heading hierarchy, a labeled textarea, real buttons and a keyboard-accessible conversation region.
- Announce connection changes through a polite status region. Use a concise alert for actionable validation failures. Avoid repeatedly announcing the entire message history.
- A chat log may use `role="log"` with polite announcements of additions; test actual screen-reader behavior, particularly when removing old entries or reconnecting.
- Keep status text and icons alongside color. Target WCAG 2.2 AA: normal-text contrast of at least 4.5:1, large-text contrast of at least 3:1, and applicable non-text contrast of at least 3:1.
- Preserve focus while new messages arrive. Do not autofocus on every reconnect or move focus into the history automatically.
- Support keyboard-only interaction, reduced motion and forced-color modes. Provide a useful `noscript` message when JavaScript is disabled.

These are acceptance targets rather than a compliance claim. Use the [WCAG 2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/) when reviewing the implemented screen.

## 6. Connection and Recovery UX

| State | Visible feedback | Composer and available action |
| --- | --- | --- |
| Connecting | “Connecting to chat…” | Disable textarea and Send until a valid `session` event arrives. |
| Connected | “Connected” | Enable textarea; enable Send only for valid content and an available local send budget. |
| Reconnecting | “Connection lost. Reconnecting — attempt N/10.” | Preserve the draft and current history; disable sending. |
| Paused | “Could not reconnect. Try again when your connection is available.” | Provide a manual Reconnect action. |
| Protocol/policy error | Explain the supported issue without printing raw server content | Stop automatic retries; allow explicit recovery after the issue is corrected. |
| Disconnected intentionally | “Disconnected” | Offer Connect; do not restart automatically. |

Create at most one active socket and one pending retry timer. Assign each attempt a generation token so an old socket's late callbacks cannot overwrite the current session. A transport `open` event alone does not enable sending: check the selected `chat.v1` subprotocol and validate the initial `session` envelope.

Use the API's full-jitter delay `random(0, min(30, 2^attempt))` seconds, pause after 10 failed retries, and reset the counter after 30 seconds of stable connection. A service restart (`1012`) permits a short jittered retry; it must not create an unlimited rapid-retry loop. Clear timers and socket handlers on intentional disconnect and page lifecycle cleanup.

Close codes `1003`, `1007`, `1008` and `1009` lead to a terminal protocol/policy state; `1011`, `1012`, `1013` and abnormal transport failures use bounded recovery. Browser WebSocket errors do not reliably expose an HTTP handshake denial body or status: show a general connection failure unless a known close code or locally validated error supports a more specific explanation. See the [API state machine](API_SPECIFICATION.md) and [MDN WebSocket client guide](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_client_applications).

## 7. Message Composition and Delivery Rules

1. Generate a valid ephemeral display name such as `Guest_a92f` using browser randomness. Keep it stable during reconnects in this page session. Names must match `^[A-Za-z0-9_-]{1,32}$`; uniqueness is not guaranteed.
2. Construct the WebSocket URL from the current page origin, using `wss:` for HTTPS and `ws:` for local HTTP. Encode the validated path component. Never hardcode an EC2 IP or backend port into browser assets.
3. Preserve the input while typing. Enter submits and Shift+Enter adds a newline; Enter during IME composition must not submit. A visible Send button provides the same action on touch devices.
4. Normalize CRLF and lone CR to LF, then trim only the boundary ASCII characters specified by the API. Count Unicode code points rather than UTF-16 code units; a native `maxlength=2000` alone does not implement this contract.
5. Reject forbidden C0/DEL controls, empty normalized input and content beyond 2,000 code points. Check UTF-8 encoded size against the 16,384-byte transport ceiling. Do not add Unicode NFKC normalization: it is absent from the authoritative API rules.
6. Send the normalized message as raw text, not a JSON command. The backend constructs event IDs, sender fields and timestamps.
7. Treat a successful browser `send()` call as local submission only. The baseline has no request ID or delivery acknowledgement, so neither socket buffering nor matching echoed text proves successful delivery.
8. Render conversation entries only from validated server broadcasts. Avoid an optimistic chat entry that would duplicate the Redis echo. On uncertain delivery, show a connection-level notice and never automatically resend the submitted text.

Proposed draft behavior: preserve an unsent draft through disconnection; clear the composer after a successful local submission so the next message can be composed. If submission throws, retain the draft. Do not create an outbox or retain every submitted message waiting for an acknowledgement the protocol does not provide.

The UI may apply a conservative local token bucket matching the backend's per-socket default of 2 messages/second with a burst of 5, and inspect `bufferedAmount` before further sends. The server remains authoritative; client checks do not prevent abuse. Choose and test a bounded browser buffering threshold during implementation rather than building an offline queue.

## 8. Rendering, History and Privacy

Validate incoming JSON, schema version, event type and required field types before touching the DOM. The first event establishes the connection-local session; subsequent `chat` and `system` events have different handling. Unknown or malformed protocol data must not be inserted into the conversation.

Create DOM elements and assign user-controlled strings with `textContent`. Do not interpret HTML, Markdown or link previews in the baseline. Show timestamps derived from `sent_at`, with an explicit local-time or UTC presentation and an accessible full date; do not use the viewer's current clock as the send time.

Retain at most 500 conversation entries in memory. Keep any event-ID bookkeeping bounded too. This is local display history, not recoverable server history: reload and missed-connection periods can lose messages. Add a visible gap notice after recovery; do not invent missing entries.

Auto-scroll only if the visitor was near the bottom before the insertion. Otherwise preserve the reading position and show “New messages below.” When trimming old entries, account for removed content height so the viewport does not jump unnecessarily. Keep the pruning notice separate from user chat content.

Keep drafts, display names and conversation text out of persistent storage, analytics, URLs and production console logs. Explain the shared, anonymous nature of the room and that connected participants can see messages; avoid promising that participants cannot copy them.

## 9. Planned Files and Logical Components

| Planned file | Responsibility |
| --- | --- |
| `frontend/index.html` | Landmarks, header, notices, conversation, composer and no-script fallback. |
| `frontend/assets/styles.css` | Theme tokens, layout, text wrapping, responsive rules and accessibility states. |
| `frontend/assets/app.js` | State transitions, socket lifecycle, validation, safe rendering and event binding. |
| `frontend/nginx.conf` | Static serving, MIME types and deliberate cache behavior. |
| `frontend/Dockerfile` | Reviewed static-server image containing only the required assets/configuration. |

Keep connection management, message validation, conversation rendering and composer behavior logically separate even if the first implementation uses one JavaScript module. Split files when that improves clarity; avoid adding a framework solely to create components.

State should contain the current connection phase, active attempt generation, socket reference, session envelope, retry timer/count, draft, recent entry bookkeeping and unread indicator. Avoid multiple independent booleans that can represent contradictory states.

## 10. Serving, Performance and Release

The frontend serves `/` and `/assets/*`; the gateway routes `/ws/*` and `/health` to backends. The browser must never contact Redis. Apply the security guide's CSP and response headers while keeping JavaScript and CSS external.

Use revalidation for HTML and for fixed-name assets. Long immutable caching requires content-versioned asset URLs and compatible release packaging; otherwise a deployment can mix old JavaScript with new markup. Test the cache policy during rollback as well as forward deployment.

Batch rendering work where necessary, bound DOM size, clean up event listeners/timers, avoid full-history re-rendering and measure long tasks under the candidate workload. The proposed 32 MiB frontend-container cap concerns the static server, not browser memory. No bundle-size, rendering-time or memory result has been measured.

## 11. Frontend Acceptance and Handoff

| Area | Evidence required |
| --- | --- |
| Happy path | Two browser sessions exchange messages through different replicas without a local duplicate echo. |
| Protocol | `chat.v1` negotiation and session-first gating; malformed/unknown envelopes handled safely. |
| Composition | Keyboard and IME behavior; line breaks, emoji, whitespace, control characters and exact boundaries. |
| Recovery | Redis/backend restart, network interruption, stale callbacks, retry exhaustion and manual retry; drafts never auto-submit. |
| UI/UX | Empty, connected, reconnecting, paused, error and disconnected states; long text, mobile keyboard and scroll preservation. |
| Accessibility | Keyboard walkthrough, contrast check, zoom/reflow and manual screen-reader review alongside automated checks. |
| Privacy/security | Literal XSS payload rendering; no secrets, message persistence or production payload logging. |
| Browsers | Record exact tested versions for Chromium, Firefox and WebKit/Safari plus representative mobile behavior. |
| Release | Asset caching, image digest, clean startup and rollback compatibility verified. |

Hand off the final visual tokens, screen-state captures, tested browser matrix, protocol fixtures and unresolved usability issues with the release evidence. Map tests to AC-01 through AC-07, AC-12 through AC-14 and the relevant requirements rather than claiming completion from this document.

## Related Guides

[Backend](BACKEND.md) | [Requirements](REQUIREMENTS.md) | [API](API_SPECIFICATION.md) | [Configuration](CONFIGURATION.md) | [Security](SECURITY.md) | [Testing](TESTING.md) | [Project structure](PROJECT_STRUCTURE.md)
