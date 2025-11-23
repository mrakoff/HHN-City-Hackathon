(() => {
  const origin = window.location.origin.replace(/\/$/, "");
  const defaultBase =
    origin.includes("localhost") || origin.includes("127.0.0.1")
      ? "http://localhost:8000/api"
      : `${origin}/api`;

  if (!window.__HHN_API_BASE) {
    window.__HHN_API_BASE = defaultBase;
  }
})();
