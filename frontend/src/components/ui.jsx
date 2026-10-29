import {useRef} from "react";
import {Icon} from "./Icon.jsx";

export function Button({children, variant = "secondary", busy = false, disabled, className = "", type = "button", ...props}) {
  return <button {...props} type={type} className={`${variant} ${className}`.trim()} disabled={disabled || busy} aria-busy={busy || undefined}>
    {busy && <span className="spinner" aria-hidden="true" />}{children}
  </button>;
}

export function Brand({caption}) {
  return <><a className="brand" href="/" aria-label="Baatchit"><span className="brand-mark" aria-hidden="true"><Icon name="chat" /></span><span>baatchit<span className="brand-period">.</span></span></a>{caption && <span className="brand-caption">{caption}</span>}</>;
}

export function Avatar({name = "?", className = "peer-avatar", online}) {
  const tone = [...name].reduce((sum, char) => sum + char.codePointAt(0), 0) % 4;
  return <span className={`${className} user-avatar`} data-tone={tone} aria-hidden="true">
    {[...name].slice(0, 2).join("").toUpperCase()}
    {online !== undefined && <span className={`peer-dot${online ? " online" : ""}`} />}
  </span>;
}

export function StatusBadge({connected, children, ...props}) {
  return <span {...props} className="status" role="status" aria-live="polite" data-connected={connected}>{children}</span>;
}

export function Feedback({error, notice, id = "notice"}) {
  if (!error && !notice) return <p id={id} className="notice" role="status" />;
  return <p id={id} className={`notice feedback${error ? " feedback-error" : ""}`} role={error ? "alert" : "status"} data-error={Boolean(error)}>
    <Icon name={error ? "info" : "check"} /><span>{error || notice}</span>
  </p>;
}

export function EmptyState({title, children, icon = "chat", action}) {
  return <div className="saved-empty"><span className="empty-illustration" aria-hidden="true"><Icon name={icon} /></span><span className="welcome-eyebrow">A LITTLE SPACE TO CONNECT</span><h2>{title}</h2><p>{children}</p>{action}</div>;
}

export function SearchField({id, label, value, onChange, placeholder, help, ...props}) {
  const input = useRef(null);
  return <div className="search-field"><label className="section-label" htmlFor={id}>{label}</label><div className="search-control">
    <Icon name="search" /><input {...props} ref={input} id={id} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} autoComplete="off" aria-describedby={help ? id + "-help" : undefined} />
    {value && <Button variant="quiet" className="icon-button" aria-label={`Clear ${label.toLowerCase()}`} onClick={() => {onChange(""); input.current?.focus();}}><Icon name="close" /></Button>}
  </div>{help && <small id={id + "-help"}>{help}</small>}</div>;
}

export function SkeletonList({label = "Loading conversations", count = 3}) {
  return <div className="skeleton-list" role="status"><span className="sr-only">{label}</span>{Array.from({length: count}, (_, i) => <div className="skeleton-row" key={i} aria-hidden="true"><span className="skeleton-avatar" /><div><span /><span /></div></div>)}</div>;
}
