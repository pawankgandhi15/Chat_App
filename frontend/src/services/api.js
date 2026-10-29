export async function api(path, options = {}) {
  const response = await fetch("/api" + path, {credentials: "same-origin", ...options,
    signal: options.signal || AbortSignal.timeout(10000),
    headers: {"Content-Type": "application/json", ...options.headers}});
  let data;
  try { data = await response.json(); }
  catch { throw new Error("Saved chats need the backend and database. Please start the full app."); }
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "The request could not be completed.");
    error.status = response.status;
    throw error;
  }
  return data;
}
