import {useState} from "react";
import {api} from "../../services/api.js";
import {Brand, Button, Feedback} from "../ui.jsx";
import {Icon} from "../Icon.jsx";

export function AuthForm({onSuccess, onCancel, initialError = ""}) {
  const [mode, setMode] = useState("login");
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {onSuccess((await api("/auth/" + mode, {method: "POST", body: JSON.stringify(Object.fromEntries(form))})).user);}
    catch (failure) {setError(failure.message);}
    finally {setBusy(false);}
  }
  return <main className="auth-page"><div className="auth-layout">
    <section className="auth-story" aria-label="Welcome to Baatchit"><Brand /><div className="auth-story-content"><span className="welcome-eyebrow">LESS NOISE. MORE CONNECTION.</span><h2>Pick up where<br />you left off<span>.</span></h2><p>A familiar place for your people and the conversations you want to keep.</p>
      <div className="auth-benefit"><Icon name="chat" /><div><strong>A conversation for two</strong><span>Find a username and say hello.</span></div></div>
      <div className="auth-benefit"><Icon name="refresh" /><div><strong>Here when you return</strong><span>Saved history across sign-ins.</span></div></div>
    </div><p className="auth-story-note">A little space to connect.</p></section>
    <section className="auth-card" aria-label="Account access"><span className="section-label">YOUR BAATCHIT ACCOUNT</span>
      <h1>{mode === "login" ? "Welcome back." : "Make yourself at home."}</h1><p>{mode === "login" ? "Sign in to your people and conversations." : "Create an account to start saving your conversations."}</p>
      <form onSubmit={submit} aria-busy={busy}>
        <label htmlFor="account-username">Username</label><input id="account-username" name="username" autoFocus autoComplete="username" required minLength={3} maxLength={32} disabled={busy} pattern="[A-Za-z0-9_-]{3,32}" placeholder="e.g. pawan" aria-describedby="username-help" />
        <small id="username-help">3–32 letters, numbers, underscores or hyphens. Other signed-in users can find your username.</small>
        <label htmlFor="account-password">Password</label><div className="password-field"><input id="account-password" name="password" type={visible ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={15} maxLength={128} disabled={busy} aria-describedby="password-help" />
          <Button variant="quiet" className="icon-button" aria-label={visible ? "Hide password" : "Show password"} aria-pressed={visible} onClick={() => setVisible(value => !value)}><Icon name="eye" /></Button></div>
        <small id="password-help">Use 15–128 characters. Password recovery is not available yet.</small>
        <Feedback error={error} /><Button variant="send" type="submit" busy={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</Button>
      </form>
      <Button variant="quiet" disabled={busy} onClick={() => {setMode(mode === "login" ? "register" : "login"); setError(""); setVisible(false);}}>{mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}</Button>
      <div className="auth-divider"><span>or keep it temporary</span></div><Button variant="quiet" disabled={busy} onClick={onCancel}>Back to temporary guest chat</Button>
    </section>
  </div></main>;
}
