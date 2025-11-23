(() => {
  const API_BASE = window.__HHN_API_BASE || "http://localhost:8000/api";

  const withBase = (path) =>
    path.startsWith("http://") || path.startsWith("https://")
      ? path
      : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

  const parseError = async (response) => {
    try {
      const payload = await response.json();
      return payload?.detail || response.statusText || "Request failed";
    } catch (err) {
      return response.statusText || "Request failed";
    }
  };

  const request = async (path, options = {}) => {
    const finalOptions = {
      credentials: options.credentials ?? "same-origin",
      ...options,
    };

    const response = await fetch(withBase(path), finalOptions);
    if (!response.ok) {
      const detail = await parseError(response);
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return response;
  };

  const getJSON = async (path, options = {}) => {
    const response = await request(path, {
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
    return response.json();
  };

  const postJSON = async (path, body, options = {}) => {
    const response = await request(path, {
      method: options.method || "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(options.headers || {}),
      },
      body: JSON.stringify(body),
    });
    return response.json();
  };

  const upload = async (path, formData, options = {}) => {
    return request(path, {
      method: options.method || "POST",
      body: formData,
      headers: options.headers || {},
    }).then((res) => res.json());
  };

  window.SharedApi = {
    API_BASE,
    request,
    getJSON,
    postJSON,
    upload,
  };
})();
