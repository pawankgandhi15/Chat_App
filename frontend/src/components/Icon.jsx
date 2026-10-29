export function Icon({name}) {
  const paths = {
    keyboard: <><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 15h10" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    eye: <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
    smile: <><circle cx="12" cy="12" r="9" /><path d="M8 14.5a4.5 4.5 0 0 0 8 0M8 9h.01M16 9h.01" /></>,
    check: <path d="m5 12 4.5 4.5L19 7" />,
    copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M15 8V4H4v11h4" /></>,
    refresh: <><path d="M20 9a8 8 0 0 0-13-3L4 9m0-5v5h5M4 15a8 8 0 0 0 13 3l3-3m0 5v-5h-5" /></>,
    arrowDown: <path d="M12 4v16m-6-6 6 6 6-6" />,
    plus: <path d="M12 5v14M5 12h14" />,
    logout: <><path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4" /></>,
    chat: <><path d="M5 5.5h14a2.5 2.5 0 0 1 2.5 2.5v7a2.5 2.5 0 0 1-2.5 2.5h-6l-4.5 3v-3H5A2.5 2.5 0 0 1 2.5 15V8A2.5 2.5 0 0 1 5 5.5Z" /><path d="M7.5 11.5h.01M12 11.5h.01M16.5 11.5h.01" strokeWidth="3" strokeLinecap="round" /></>,
    people: <><circle cx="9" cy="8" r="3" /><path d="M3.5 19v-1a5.5 5.5 0 0 1 11 0v1H3.5ZM16 5.5a3 3 0 0 1 0 5.8M16 13.5a5 5 0 0 1 4.5 5v.5h-3" /></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2" /></>,
    send: <><path d="m21 3-7.5 18-3.2-7.3L3 10.5 21 3ZM10.3 13.7 21 3" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" strokeLinecap="round" /></>,
    sparkle: <><path d="M12 2.5c.6 5.2 2.3 6.9 7.5 7.5-5.2.6-6.9 2.3-7.5 7.5C11.4 12.3 9.7 10.6 4.5 10c5.2-.6 6.9-2.3 7.5-7.5ZM19 15l.6 1.9L21.5 17l-1.9.6L19 19.5l-.6-1.9-1.9-.6 1.9-.1L19 15Z" /></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
