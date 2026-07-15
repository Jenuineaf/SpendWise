const API_BASE = "/api/v1";

const TokenStore = {
  get access() { return localStorage.getItem("sw_access_token"); },
  get refresh() { return localStorage.getItem("sw_refresh_token"); },
  set(access, refresh) {
    localStorage.setItem("sw_access_token", access);
    if (refresh) localStorage.setItem("sw_refresh_token", refresh);
  },
  clear() {
    localStorage.removeItem("sw_access_token");
    localStorage.removeItem("sw_refresh_token");
  },
};

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : "Request failed");
    this.status = status;
    this.detail = detail;
  }
}

let refreshingPromise = null;

async function refreshAccessToken() {
  if (!TokenStore.refresh) throw new ApiError(401, "No refresh token");
  if (!refreshingPromise) {
    refreshingPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: TokenStore.refresh }),
    })
      .then(async (res) => {
        if (!res.ok) throw new ApiError(res.status, "Session expired");
        const data = await res.json();
        TokenStore.set(data.access_token, data.refresh_token);
        return data.access_token;
      })
      .finally(() => {
        refreshingPromise = null;
      });
  }
  return refreshingPromise;
}

async function request(path, { method = "GET", body, isForm = false, retry = true } = {}) {
  const headers = {};
  if (!isForm) headers["Content-Type"] = "application/json";
  if (TokenStore.access) headers["Authorization"] = `Bearer ${TokenStore.access}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  });

  if (res.status === 401 && retry && TokenStore.refresh) {
    try {
      await refreshAccessToken();
      return request(path, { method, body, isForm, retry: false });
    } catch {
      TokenStore.clear();
      window.dispatchEvent(new CustomEvent("sw:unauthorized"));
      throw new ApiError(401, "Session expired");
    }
  }

  if (res.status === 401) {
    TokenStore.clear();
    window.dispatchEvent(new CustomEvent("sw:unauthorized"));
  }

  if (res.status === 204) return null;

  const contentType = res.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await res.json() : await res.blob();

  if (!res.ok) {
    const detail = payload && payload.detail ? payload.detail : "Something went wrong";
    throw new ApiError(res.status, detail);
  }
  return payload;
}

const Api = {
  // auth
  signup: (email, password, full_name) =>
    request("/auth/signup", { method: "POST", body: { email, password, full_name } }),
  login: async (email, password) => {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const res = await fetch(`${API_BASE}/auth/login`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new ApiError(res.status, data.detail || "Login failed");
    TokenStore.set(data.access_token, data.refresh_token);
    return data;
  },
  logout: () => TokenStore.clear(),
  me: () => request("/auth/me"),
  updateMe: (data) => request("/auth/me", { method: "PATCH", body: data }),

  // categories
  listCategories: () => request("/categories"),
  createCategory: (data) => request("/categories", { method: "POST", body: data }),
  updateCategory: (id, data) => request(`/categories/${id}`, { method: "PATCH", body: data }),
  deleteCategory: (id) => request(`/categories/${id}`, { method: "DELETE" }),

  // expenses
  listExpenses: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== ""));
    return request(`/expenses?${qs.toString()}`);
  },
  createExpense: (data) => request("/expenses", { method: "POST", body: data }),
  updateExpense: (id, data) => request(`/expenses/${id}`, { method: "PATCH", body: data }),
  deleteExpense: (id) => request(`/expenses/${id}`, { method: "DELETE" }),

  // budgets
  listBudgets: (year, month) => request(`/budgets?year=${year}&month=${month}`),
  createBudget: (data) => request("/budgets", { method: "POST", body: data }),
  updateBudget: (id, data) => request(`/budgets/${id}`, { method: "PATCH", body: data }),
  deleteBudget: (id) => request(`/budgets/${id}`, { method: "DELETE" }),

  // recurring
  listRecurring: () => request("/recurring"),
  createRecurring: (data) => request("/recurring", { method: "POST", body: data }),
  updateRecurring: (id, data) => request(`/recurring/${id}`, { method: "PATCH", body: data }),
  deleteRecurring: (id) => request(`/recurring/${id}`, { method: "DELETE" }),

  // import
  importCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/import/csv", { method: "POST", body: form, isForm: true });
  },

  // analytics
  monthlyTrend: (months = 6) => request(`/analytics/monthly-trend?months=${months}`),
  categoryBreakdown: (year, month) => request(`/analytics/category-breakdown?year=${year}&month=${month}`),
  topMerchants: (year, month, limit = 10) =>
    request(`/analytics/top-merchants?year=${year}&month=${month}&limit=${limit}`),
  dailySpend: (year, month) => request(`/analytics/daily-spend?year=${year}&month=${month}`),

  // alerts
  listAlerts: () => request("/alerts"),

  // advisor
  askAdvisor: (question) => request("/advisor/ask", { method: "POST", body: { question } }),

  // savings goals
  listGoals: () => request("/savings-goals"),
  createGoal: (data) => request("/savings-goals", { method: "POST", body: data }),
  updateGoal: (id, data) => request(`/savings-goals/${id}`, { method: "PATCH", body: data }),
  deleteGoal: (id) => request(`/savings-goals/${id}`, { method: "DELETE" }),

  // export
  exportCsvUrl: () => `${API_BASE}/export/expenses.csv`,
  exportPdfUrl: (year, month) => `${API_BASE}/export/monthly-report.pdf?year=${year}&month=${month}`,
};

async function downloadWithAuth(url, filename) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${TokenStore.access}` } });
  if (!res.ok) throw new ApiError(res.status, "Export failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
