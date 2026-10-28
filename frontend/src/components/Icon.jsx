export function Icon({name}) {
  const paths = {
    chat: <><path d="M5 5.5h14a2.5 2.5 0 0 1 2.5 2.5v7a2.5 2.5 0 0 1-2.5 2.5h-6l-4.5 3v-3H5A2.5 2.5 0 0 1 2.5 15V8A2.5 2.5 0 0 1 5 5.5Z" /><path d="M7.5 11.5h.01M12 11.5h.01M16.5 11.5h.01" strokeWidth="3" strokeLinecap="round" /></>,
    people: <><circle cx="9" cy="8" r="3" /><path d="M3.5 19v-1a5.5 5.5 0 0 1 11 0v1H3.5ZM16 5.5a3 3 0 0 1 0 5.8M16 13.5a5 5 0 0 1 4.5 5v.5h-3" /></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2" /></>,
    send: <><path d="m21 3-7.5 18-3.2-7.3L3 10.5 21 3ZM10.3 13.7 21 3" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" strokeLinecap="round" /></>,
    sparkle: <><path d="M12 2.5c.6 5.2 2.3 6.9 7.5 7.5-5.2.6-6.9 2.3-7.5 7.5C11.4 12.3 9.7 10.6 4.5 10c5.2-.6 6.9-2.3 7.5-7.5ZM19 15l.6 1.9L21.5 17l-1.9.6L19 19.5l-.6-1.9-1.9-.6 1.9-.1L19 15Z" /></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
