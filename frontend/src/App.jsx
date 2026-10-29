import {useCallback, useEffect, useState} from "react";
import {AccountChat} from "./AccountChat.jsx";
import {GuestApp} from "./GuestApp.jsx";
import {AuthForm} from "./components/accounts/AuthForm.jsx";
import {api} from "./services/api.js";

export function App() {
  const [user, setUser] = useState(null);
  const [auth, setAuth] = useState(false);
  const [authError, setAuthError] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let active = true;
    api("/auth/me").then(data => {if (active) setUser(data.user);}).catch(() => {})
      .finally(() => {if (active) setReady(true);});
    return () => {active = false;};
  }, []);
  const expired = useCallback(message => {
    setUser(null); setAuth(true); setAuthError(message || "Your session expired. Sign in again to see your saved conversations.");
  }, []);
  if (!ready) return <main className="auth-page"><p role="status">Opening Baatchit…</p></main>;
  if (user) return <AccountChat key={user.id} user={user} onExpired={expired} onLogout={() => setUser(null)} />;
  if (auth) return <AuthForm initialError={authError} onSuccess={account => {setUser(account); setAuth(false); setAuthError("");}} onCancel={() => setAuth(false)} />;
  return <GuestApp onSignIn={() => {setAuth(true); setAuthError("");}} />;
}
