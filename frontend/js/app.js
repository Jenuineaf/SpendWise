/* ============================================================
   SpendWise frontend — app state, routing, and view logic.
   No build step, no framework: plain DOM + fetch, talking to
   the FastAPI backend under /api/v1 (same origin).
   ============================================================ */

const state = {
  user: null,
  categories: [],
  expensesPage: 1,
  expensesPageSize: 10,
  budgetsMonth: new Date(),
  analyticsMonth: new Date(),
};

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];

/* ---------------------------- helpers ---------------------------- */

function formatApiError(err) {
  if (!err) return "Something went wrong.";
  const d = err.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e.msg || JSON.stringify(e)).join("; ");
  return err.message || "Something went wrong.";
}

function toast(message, type = "default") {
  const stack = document.getElementById("toast-stack");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function categoryName(id) {
  const c = state.categories.find((c) => c.id === id);
  return c ? c.name : "—";
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

/* ---------------------------- modal ---------------------------- */

function openModal(html) {
  document.getElementById("modal-content").innerHTML = html;
  document.getElementById("modal-backdrop").classList.add("visible");
}
function closeModal() {
  document.getElementById("modal-backdrop").classList.remove("visible");
  document.getElementById("modal-content").innerHTML = "";
}
document.getElementById("modal-backdrop").addEventListener("click", (e) => {
  if (e.target.id === "modal-backdrop") closeModal();
});

/* ---------------------------- auth ---------------------------- */

document.querySelectorAll(".auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".auth-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const isLogin = tab.dataset.tab === "login";
    document.getElementById("login-form").classList.toggle("hidden", !isLogin);
    document.getElementById("signup-form").classList.toggle("hidden", isLogin);
    hideAuthError();
  });
});

function showAuthError(msg) {
  const box = document.getElementById("auth-error");
  box.textContent = msg;
  box.classList.add("visible");
}
function hideAuthError() {
  document.getElementById("auth-error").classList.remove("visible");
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAuthError();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  try {
    await Api.login(email, password);
    await bootApp();
  } catch (err) {
    showAuthError(formatApiError(err));
  }
});

document.getElementById("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAuthError();
  const full_name = document.getElementById("signup-name").value.trim() || undefined;
  const email = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value;
  try {
    await Api.signup(email, password, full_name);
    await Api.login(email, password);
    await bootApp();
  } catch (err) {
    showAuthError(formatApiError(err));
  }
});

document.getElementById("btn-logout").addEventListener("click", () => {
  Api.logout();
  location.reload();
});
window.addEventListener("sw:unauthorized", () => {
  toast("Your session expired — please log in again.", "error");
  location.reload();
});

/* ---------------------------- navigation ---------------------------- */

const VIEW_TITLES = {
  dashboard: ["Dashboard", "Your spending at a glance"],
  expenses: ["Expenses", "Every rupee, logged"],
  categories: ["Categories", "Organize how you spend"],
  budgets: ["Budgets", "Set limits, stay on track"],
  recurring: ["Recurring expenses", "Bills that repeat, handled automatically"],
  import: ["Import CSV", "Bring in a bank or UPI statement"],
  analytics: ["Analytics", "Trends, categories, and merchants"],
  goals: ["Savings goals", "What you're working towards"],
  advisor: ["Advisor", "Ask a question about your money"],
  settings: ["Settings", "Profile and data export"],
};

function goToView(name) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  const [title, sub] = VIEW_TITLES[name] || [name, ""];
  document.getElementById("page-title").textContent = title;
  document.getElementById("page-sub").textContent = sub;
  document.getElementById("sidebar").classList.remove("open");
  loadView(name);
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => goToView(btn.dataset.view));
});
document.querySelectorAll("[data-nav]").forEach((elx) => {
  elx.addEventListener("click", () => goToView(elx.dataset.nav));
});
document.getElementById("menu-toggle").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});
document.getElementById("btn-quick-add").addEventListener("click", () => openExpenseForm());

function loadView(name) {
  const loaders = {
    dashboard: loadDashboard,
    expenses: loadExpenses,
    categories: loadCategories,
    budgets: loadBudgets,
    recurring: loadRecurring,
    goals: loadGoals,
    analytics: loadAnalytics,
  };
  if (loaders[name]) loaders[name]();
}

/* ---------------------------- bootstrap ---------------------------- */

async function bootApp() {
  try {
    state.user = await Api.me();
  } catch {
    return; // stays on auth screen
  }
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  document.getElementById("sidebar-user-email").textContent = state.user.email;
  state.categories = await Api.listCategories();
  goToView("dashboard");
}

(async function init() {
  if (TokenStore.access) await bootApp();
})();

/* ============================================================
   DASHBOARD
   ============================================================ */

function renderIncomeOverview(container, { income, totalBudgeted, totalSpent }) {
  if (income == null) {
    container.innerHTML = `
      <div class="empty-state">Set your monthly income to see what's left to budget and spend.</div>
      <div class="form-actions" style="justify-content:center; margin-top:4px;">
        <button class="btn btn-gold btn-sm" id="income-overview-set-btn">Set monthly income</button>
      </div>
    `;
    document.getElementById("income-overview-set-btn").addEventListener("click", () => goToView("settings"));
    return;
  }

  const unallocated = income - totalBudgeted;
  const remaining = income - totalSpent;
  const allocPct = income > 0 ? Math.min((totalBudgeted / income) * 100, 100) : 0;
  const spendPct = income > 0 ? Math.min((totalSpent / income) * 100, 100) : 0;
  const allocClass = totalBudgeted > income ? "critical" : "good";
  const spendClass = totalSpent >= income ? "critical" : totalSpent >= income * 0.8 ? "warning" : "good";

  container.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:22px;">
      <div class="flex-between">
        <span class="text-sm text-muted">Monthly income</span>
        <strong style="font-size:19px;">${formatMoney(income)}</strong>
      </div>

      <div>
        <div class="flex-between text-sm" style="margin-bottom:6px;">
          <span>Budgeted across categories</span>
          <span>${formatMoney(totalBudgeted)}</span>
        </div>
        <div class="progress-track"><div class="progress-fill ${allocClass}" style="width:${allocPct}%"></div></div>
        <div class="budget-card-figures" style="margin-top:6px; justify-content:flex-end;">
          <span>${
            unallocated >= 0
              ? formatMoney(unallocated) + " left to budget"
              : formatMoney(-unallocated) + " over-allocated"
          }</span>
        </div>
      </div>

      <div>
        <div class="flex-between text-sm" style="margin-bottom:6px;">
          <span>Spent so far this month</span>
          <span>${formatMoney(totalSpent)}</span>
        </div>
        <div class="progress-track"><div class="progress-fill ${spendClass}" style="width:${spendPct}%"></div></div>
        <div class="budget-card-figures" style="margin-top:6px; justify-content:flex-end;">
          <span>${
            remaining >= 0
              ? formatMoney(remaining) + " remaining from income"
              : formatMoney(-remaining) + " over your income"
          }</span>
        </div>
      </div>
    </div>
  `;
}

async function loadDashboard() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  const [trend, breakdown, expensesPage, budgets] = await Promise.all([
    Api.monthlyTrend(6),
    Api.categoryBreakdown(year, month),
    Api.listExpenses({ page: 1, page_size: 5 }),
    Api.listBudgets(year, month),
  ]);

  const totalSpent = breakdown.reduce((sum, c) => sum + Number(c.total), 0);
  const totalBudget = budgets.reduce((sum, b) => sum + Number(b.amount), 0);
  const totalRemaining = budgets.reduce((sum, b) => sum + Number(b.remaining), 0);
  const topCategory = breakdown[0];
  let alertsCount = 0;
  try {
    const alerts = await Api.listAlerts();
    const thisMonthBudgetIds = new Set(budgets.map((b) => b.id));
    alertsCount = alerts.filter((a) => thisMonthBudgetIds.has(a.budget_id)).length;
  } catch { /* non-critical */ }

  document.getElementById("dashboard-stats").innerHTML = `
    <div class="stat-tile">
      <div class="stat-label">Spent this month</div>
      <div class="stat-value">${formatMoney(totalSpent)}</div>
      <div class="stat-delta">${breakdown.length} categor${breakdown.length === 1 ? "y" : "ies"} active</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Budget remaining</div>
      <div class="stat-value">${budgets.length ? formatMoney(totalRemaining) : "—"}</div>
      <div class="stat-delta">${budgets.length ? `of ${formatMoney(totalBudget)} budgeted` : "No budgets set yet"}</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Top category</div>
      <div class="stat-value">${topCategory ? topCategory.category_name : "—"}</div>
      <div class="stat-delta">${topCategory ? formatMoney(topCategory.total) + " so far" : "No spending yet"}</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Budget alerts</div>
      <div class="stat-value">${alertsCount}</div>
      <div class="stat-delta">${alertsCount ? "triggered this month" : "All within budget"}</div>
    </div>
  `;

  renderIncomeOverview(document.getElementById("dashboard-income-overview"), {
    income: state.user.monthly_income != null ? Number(state.user.monthly_income) : null,
    totalBudgeted: totalBudget,
    totalSpent,
  });

  const trendPoints = trend.map((p) => ({ ...p, label: MONTH_NAMES[p.month - 1].slice(0, 3) }));
  renderLineChart(document.getElementById("dashboard-trend-chart"), trendPoints, { xKey: "month", yKey: "total", xLabel: "label" });

  renderBarList(document.getElementById("dashboard-breakdown-chart"), breakdown.slice(0, 6), {
    labelKey: "category_name", valueKey: "total",
  });

  const tbody = document.querySelector("#dashboard-recent-table tbody");
  if (expensesPage.items.length === 0) {
    tbody.innerHTML = `<tr><td class="empty-state">No expenses yet — add your first one.</td></tr>`;
  } else {
    tbody.innerHTML = expensesPage.items
      .map(
        (x) => `<tr>
          <td>${x.date}</td>
          <td><span class="category-chip">${categoryName(x.category_id)}</span></td>
          <td>${x.merchant || "<span class='text-muted'>—</span>"}</td>
          <td class="num">${formatMoney(x.amount)}</td>
        </tr>`
      )
      .join("");
  }
}

/* ============================================================
   EXPENSES
   ============================================================ */

function populateCategorySelect(select, selectedId) {
  select.innerHTML = state.categories
    .map((c) => `<option value="${c.id}" ${c.id === selectedId ? "selected" : ""}>${c.name}</option>`)
    .join("");
}

async function loadExpenses() {
  const filterSelect = document.getElementById("filter-category");
  if (filterSelect.dataset.populated !== "1") {
    filterSelect.innerHTML =
      `<option value="">All categories</option>` +
      state.categories.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
    filterSelect.dataset.populated = "1";
  }

  const params = {
    page: state.expensesPage,
    page_size: state.expensesPageSize,
    category_id: filterSelect.value || undefined,
    date_from: document.getElementById("filter-date-from").value || undefined,
    date_to: document.getElementById("filter-date-to").value || undefined,
  };

  const data = await Api.listExpenses(params);
  const tbody = document.getElementById("expenses-table-body");

  if (data.items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No expenses match these filters.</td></tr>`;
  } else {
    tbody.innerHTML = data.items
      .map(
        (x) => `<tr>
          <td>${x.date}</td>
          <td><span class="category-chip">${categoryName(x.category_id)}</span></td>
          <td>${x.merchant || "<span class='text-muted'>—</span>"}</td>
          <td>${x.note || "<span class='text-muted'>—</span>"}</td>
          <td class="num">${formatMoney(x.amount)}</td>
          <td class="row-actions">
            <button class="btn btn-ghost btn-sm" data-edit="${x.id}">Edit</button>
            <button class="btn btn-danger btn-sm" data-del="${x.id}">Delete</button>
          </td>
        </tr>`
      )
      .join("");

    tbody.querySelectorAll("[data-edit]").forEach((b) =>
      b.addEventListener("click", () => openExpenseForm(data.items.find((x) => x.id === b.dataset.edit)))
    );
    tbody.querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", () => deleteExpense(b.dataset.del))
    );
  }

  const pages = data.pages || 1;
  document.getElementById("expenses-pagination").innerHTML = `
    <span>Page ${data.page} of ${pages || 1} · ${data.total} total</span>
    <div class="flex-gap">
      <button class="btn btn-ghost btn-sm" id="pg-prev" ${data.page <= 1 ? "disabled" : ""}>← Prev</button>
      <button class="btn btn-ghost btn-sm" id="pg-next" ${data.page >= pages ? "disabled" : ""}>Next →</button>
    </div>
  `;
  document.getElementById("pg-prev")?.addEventListener("click", () => { state.expensesPage--; loadExpenses(); });
  document.getElementById("pg-next")?.addEventListener("click", () => { state.expensesPage++; loadExpenses(); });
}

["filter-category", "filter-date-from", "filter-date-to"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => { state.expensesPage = 1; loadExpenses(); });
});
document.getElementById("btn-clear-filters").addEventListener("click", () => {
  document.getElementById("filter-category").value = "";
  document.getElementById("filter-date-from").value = "";
  document.getElementById("filter-date-to").value = "";
  state.expensesPage = 1;
  loadExpenses();
});
document.getElementById("btn-add-expense").addEventListener("click", () => openExpenseForm());

function openExpenseForm(existing) {
  const isEdit = Boolean(existing);
  openModal(`
    <div class="modal-header"><h3>${isEdit ? "Edit expense" : "Add expense"}</h3><button class="modal-close" id="modal-close">&times;</button></div>
    <form class="auth-form" id="expense-form">
      <div class="form-grid">
        <div class="field">
          <label>Amount (₹)</label>
          <input type="number" min="0.01" step="0.01" id="ex-amount" required value="${isEdit ? existing.amount : ""}" />
        </div>
        <div class="field">
          <label>Category</label>
          <select id="ex-category" required></select>
        </div>
      </div>
      <div class="form-grid">
        <div class="field">
          <label>Date</label>
          <input type="date" id="ex-date" required value="${isEdit ? existing.date : todayIso()}" />
        </div>
        <div class="field">
          <label>Merchant <span class="text-muted">(optional)</span></label>
          <input type="text" id="ex-merchant" value="${isEdit ? (existing.merchant || "") : ""}" />
        </div>
      </div>
      <div class="field">
        <label>Note <span class="text-muted">(optional)</span></label>
        <input type="text" id="ex-note" value="${isEdit ? (existing.note || "") : ""}" />
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost" id="modal-cancel">Cancel</button>
        <button type="submit" class="btn btn-primary">${isEdit ? "Save changes" : "Add expense"}</button>
      </div>
    </form>
  `);
  populateCategorySelect(document.getElementById("ex-category"), isEdit ? existing.category_id : undefined);
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-cancel").addEventListener("click", closeModal);
  document.getElementById("expense-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      amount: document.getElementById("ex-amount").value,
      category_id: document.getElementById("ex-category").value,
      date: document.getElementById("ex-date").value,
      merchant: document.getElementById("ex-merchant").value || null,
      note: document.getElementById("ex-note").value || null,
    };
    try {
      if (isEdit) await Api.updateExpense(existing.id, payload);
      else await Api.createExpense(payload);
      closeModal();
      toast(isEdit ? "Expense updated." : "Expense added.", "success");
      loadExpenses();
      loadDashboard();
    } catch (err) {
      toast(formatApiError(err), "error");
    }
  });
}

async function deleteExpense(id) {
  if (!confirm("Delete this expense?")) return;
  try {
    await Api.deleteExpense(id);
    toast("Expense deleted.", "success");
    loadExpenses();
  } catch (err) {
    toast(formatApiError(err), "error");
  }
}

/* ============================================================
   CATEGORIES
   ============================================================ */

async function loadCategories() {
  state.categories = await Api.listCategories();
  const tbody = document.getElementById("categories-table-body");
  tbody.innerHTML = state.categories
    .map(
      (c) => `<tr>
        <td>${c.name}</td>
        <td>${c.is_default ? '<span class="pill pill-neutral">Default</span>' : '<span class="pill pill-neutral">Custom</span>'}</td>
        <td class="row-actions">
          <button class="btn btn-ghost btn-sm" data-edit="${c.id}">Rename</button>
          <button class="btn btn-danger btn-sm" data-del="${c.id}">Delete</button>
        </td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll("[data-edit]").forEach((b) =>
    b.addEventListener("click", () => openCategoryForm(state.categories.find((c) => c.id === b.dataset.edit)))
  );
  tbody.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => deleteCategory(b.dataset.del)));
}

document.getElementById("btn-add-category").addEventListener("click", () => openCategoryForm());

function openCategoryForm(existing) {
  const isEdit = Boolean(existing);
  openModal(`
    <div class="modal-header"><h3>${isEdit ? "Rename category" : "New category"}</h3><button class="modal-close" id="modal-close">&times;</button></div>
    <form class="auth-form" id="category-form">
      <div class="field">
        <label>Name</label>
        <input type="text" id="cat-name" required value="${isEdit ? existing.name : ""}" />
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost" id="modal-cancel">Cancel</button>
        <button type="submit" class="btn btn-primary">${isEdit ? "Save" : "Create"}</button>
      </div>
    </form>
  `);
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-cancel").addEventListener("click", closeModal);
  document.getElementById("category-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("cat-name").value.trim();
    try {
      if (isEdit) await Api.updateCategory(existing.id, { name });
      else await Api.createCategory({ name });
      closeModal();
      toast("Saved.", "success");
      loadCategories();
    } catch (err) {
      toast(formatApiError(err), "error");
    }
  });
}

async function deleteCategory(id) {
  if (!confirm("Delete this category? This only works if no expenses use it.")) return;
  try {
    await Api.deleteCategory(id);
    toast("Category deleted.", "success");
    loadCategories();
  } catch (err) {
    toast(formatApiError(err), "error");
  }
}

/* ============================================================
   BUDGETS
   ============================================================ */

function budgetStatusClass(pct) {
  if (pct >= 100) return "critical";
  if (pct >= 80) return "warning";
  return "good";
}

async function loadBudgets() {
  const year = state.budgetsMonth.getFullYear();
  const month = state.budgetsMonth.getMonth() + 1;
  document.getElementById("budgets-month-label").textContent = `Budgets — ${MONTH_NAMES[month - 1]} ${year}`;

  const budgets = await Api.listBudgets(year, month);
  const budgetedIds = new Set(budgets.map((b) => b.category_id));

  const cards = budgets
    .map((b) => {
      const cls = budgetStatusClass(b.percent_used);
      return `
      <div class="budget-card">
        <div class="budget-card-top">
          <strong>${categoryName(b.category_id)}</strong>
          <span class="pill pill-${cls}"><span class="pill-dot"></span>${Math.round(b.percent_used)}%</span>
        </div>
        <div class="progress-track"><div class="progress-fill ${cls}" style="width:${Math.min(b.percent_used, 100)}%"></div></div>
        <div class="budget-card-figures">
          <span>${formatMoney(b.spent)} spent</span>
          <span>${formatMoney(b.amount)} budget</span>
        </div>
        <div class="row-actions">
          <button class="btn btn-ghost btn-sm" data-edit-budget="${b.id}" data-amount="${b.amount}">Edit</button>
          <button class="btn btn-danger btn-sm" data-del-budget="${b.id}">Delete</button>
        </div>
      </div>`;
    })
    .join("");

  const unbudgeted = state.categories
    .filter((c) => !budgetedIds.has(c.id))
    .map(
      (c) => `
      <div class="budget-card" style="align-items:center; justify-content:center; text-align:center; gap:8px;">
        <strong>${c.name}</strong>
        <span class="text-muted text-sm">No budget set for this month</span>
        <button class="btn btn-gold btn-sm" data-set-budget="${c.id}">Set budget</button>
      </div>`
    )
    .join("");

  document.getElementById("budgets-grid").innerHTML =
    cards + unbudgeted || `<div class="empty-state">No categories yet — add one first.</div>`;

  document.querySelectorAll("[data-edit-budget]").forEach((b) =>
    b.addEventListener("click", () => openBudgetForm({ id: b.dataset.editBudget, amount: b.dataset.amount }))
  );
  document.querySelectorAll("[data-del-budget]").forEach((b) => b.addEventListener("click", () => deleteBudget(b.dataset.delBudget)));
  document.querySelectorAll("[data-set-budget]").forEach((b) =>
    b.addEventListener("click", () => openBudgetForm(null, b.dataset.setBudget))
  );
}

document.getElementById("budgets-prev-month").addEventListener("click", () => {
  state.budgetsMonth.setMonth(state.budgetsMonth.getMonth() - 1);
  loadBudgets();
});
document.getElementById("budgets-next-month").addEventListener("click", () => {
  state.budgetsMonth.setMonth(state.budgetsMonth.getMonth() + 1);
  loadBudgets();
});
document.getElementById("btn-add-budget").addEventListener("click", () => openBudgetForm());

function openBudgetForm(existing, presetCategoryId) {
  const isEdit = Boolean(existing);
  const year = state.budgetsMonth.getFullYear();
  const month = state.budgetsMonth.getMonth() + 1;
  openModal(`
    <div class="modal-header"><h3>${isEdit ? "Edit budget" : "Set a budget"}</h3><button class="modal-close" id="modal-close">&times;</button></div>
    <form class="auth-form" id="budget-form">
      <div class="field">
        <label>Category</label>
        <select id="bud-category" ${isEdit ? "disabled" : ""}></select>
      </div>
      <div class="field">
        <label>Month</label>
        <input type="text" value="${MONTH_NAMES[month - 1]} ${year}" disabled />
      </div>
      <div class="field">
        <label>Amount (₹)</label>
        <input type="number" min="0.01" step="0.01" id="bud-amount" required value="${isEdit ? existing.amount : ""}" />
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost" id="modal-cancel">Cancel</button>
        <button type="submit" class="btn btn-primary">${isEdit ? "Save" : "Set budget"}</button>
      </div>
    </form>
  `);
  populateCategorySelect(document.getElementById("bud-category"), presetCategoryId);
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-cancel").addEventListener("click", closeModal);
  document.getElementById("budget-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      if (isEdit) {
        await Api.updateBudget(existing.id, { amount: document.getElementById("bud-amount").value });
      } else {
        await Api.createBudget({
          category_id: document.getElementById("bud-category").value,
          year, month,
          amount: document.getElementById("bud-amount").value,
        });
      }
      closeModal();
      toast("Budget saved.", "success");
      loadBudgets();
    } catch (err) {
      toast(formatApiError(err), "error");
    }
  });
}

async function deleteBudget(id) {
  if (!confirm("Delete this budget?")) return;
  try {
    await Api.deleteBudget(id);
    toast("Budget deleted.", "success");
    loadBudgets();
  } catch (err) {
    toast(formatApiError(err), "error");
  }
}

/* ============================================================
   RECURRING
   ============================================================ */

async function loadRecurring() {
  const rules = await Api.listRecurring();
  const tbody = document.getElementById("recurring-table-body");
  if (rules.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No recurring rules yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = rules
    .map(
      (r) => `<tr>
        <td><span class="category-chip">${categoryName(r.category_id)}</span></td>
        <td>${r.merchant || r.note || "<span class='text-muted'>—</span>"}</td>
        <td class="num">${formatMoney(r.amount)}</td>
        <td style="text-transform:capitalize;">${r.cadence}</td>
        <td>${r.next_run}</td>
        <td>${r.is_active ? '<span class="pill pill-good"><span class="pill-dot"></span>Active</span>' : '<span class="pill pill-neutral">Paused</span>'}</td>
        <td class="row-actions">
          <button class="btn btn-ghost btn-sm" data-toggle="${r.id}" data-active="${r.is_active}">${r.is_active ? "Pause" : "Resume"}</button>
          <button class="btn btn-danger btn-sm" data-del="${r.id}">Delete</button>
        </td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll("[data-toggle]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        await Api.updateRecurring(b.dataset.toggle, { is_active: b.dataset.active !== "true" });
        loadRecurring();
      } catch (err) {
        toast(formatApiError(err), "error");
      }
    })
  );
  tbody.querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("Delete this recurring rule?")) return;
      try {
        await Api.deleteRecurring(b.dataset.del);
        toast("Rule deleted.", "success");
        loadRecurring();
      } catch (err) {
        toast(formatApiError(err), "error");
      }
    })
  );
}

document.getElementById("btn-add-recurring").addEventListener("click", () => openRecurringForm());

function openRecurringForm() {
  openModal(`
    <div class="modal-header"><h3>New recurring rule</h3><button class="modal-close" id="modal-close">&times;</button></div>
    <form class="auth-form" id="recurring-form">
      <div class="form-grid">
        <div class="field">
          <label>Category</label>
          <select id="rec-category" required></select>
        </div>
        <div class="field">
          <label>Amount (₹)</label>
          <input type="number" min="0.01" step="0.01" id="rec-amount" required />
        </div>
      </div>
      <div class="form-grid">
        <div class="field">
          <label>Cadence</label>
          <select id="rec-cadence">
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly" selected>Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
        </div>
        <div class="field">
          <label>Next run</label>
          <input type="date" id="rec-next-run" required value="${todayIso()}" />
        </div>
      </div>
      <div class="field">
        <label>Merchant / note <span class="text-muted">(optional)</span></label>
        <input type="text" id="rec-merchant" />
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost" id="modal-cancel">Cancel</button>
        <button type="submit" class="btn btn-primary">Create rule</button>
      </div>
    </form>
  `);
  populateCategorySelect(document.getElementById("rec-category"));
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-cancel").addEventListener("click", closeModal);
  document.getElementById("recurring-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await Api.createRecurring({
        category_id: document.getElementById("rec-category").value,
        amount: document.getElementById("rec-amount").value,
        cadence: document.getElementById("rec-cadence").value,
        next_run: document.getElementById("rec-next-run").value,
        merchant: document.getElementById("rec-merchant").value || null,
      });
      closeModal();
      toast("Recurring rule created.", "success");
      loadRecurring();
    } catch (err) {
      toast(formatApiError(err), "error");
    }
  });
}

/* ============================================================
   IMPORT
   ============================================================ */

document.getElementById("btn-do-import").addEventListener("click", async () => {
  const fileInput = document.getElementById("import-file");
  const file = fileInput.files[0];
  if (!file) { toast("Choose a CSV file first.", "error"); return; }
  const resultBox = document.getElementById("import-result");
  resultBox.innerHTML = `<div class="loading-row"><div class="spinner"></div>Importing…</div>`;
  try {
    const summary = await Api.importCsv(file);
    resultBox.innerHTML = `
      <div class="stat-grid" style="margin-bottom:16px;">
        <div class="stat-tile"><div class="stat-label">Rows found</div><div class="stat-value">${summary.rows_total}</div></div>
        <div class="stat-tile"><div class="stat-label">Imported</div><div class="stat-value">${summary.rows_imported}</div></div>
        <div class="stat-tile"><div class="stat-label">Skipped</div><div class="stat-value">${summary.rows_skipped}</div></div>
      </div>
      ${
        summary.skipped_reasons.length
          ? `<div class="table-wrap"><table><thead><tr><th>Row</th><th>Reason</th></tr></thead><tbody>${summary.skipped_reasons
              .map((s) => `<tr><td>${s.row_number}</td><td>${s.reason}</td></tr>`)
              .join("")}</tbody></table></div>`
          : ""
      }
    `;
    toast(`Imported ${summary.rows_imported} expense(s).`, "success");
    fileInput.value = "";
  } catch (err) {
    resultBox.innerHTML = "";
    toast(formatApiError(err), "error");
  }
});

/* ============================================================
   ANALYTICS
   ============================================================ */

async function loadAnalytics() {
  const year = state.analyticsMonth.getFullYear();
  const month = state.analyticsMonth.getMonth() + 1;
  document.getElementById("analytics-month-label").textContent = `Analytics — ${MONTH_NAMES[month - 1]} ${year}`;

  const [trend, breakdown, merchants, daily] = await Promise.all([
    Api.monthlyTrend(6),
    Api.categoryBreakdown(year, month),
    Api.topMerchants(year, month, 8),
    Api.dailySpend(year, month),
  ]);

  const trendPoints = trend.map((p) => ({ ...p, label: MONTH_NAMES[p.month - 1].slice(0, 3) }));
  renderLineChart(document.getElementById("analytics-trend-chart"), trendPoints, { xKey: "month", yKey: "total", xLabel: "label" });
  renderBarList(document.getElementById("analytics-breakdown-chart"), breakdown, { labelKey: "category_name", valueKey: "total" });
  renderBarList(document.getElementById("analytics-merchants-chart"), merchants, { labelKey: "merchant", valueKey: "total" });
  renderDailyBarChart(document.getElementById("analytics-daily-chart"), daily, { xKey: "day", yKey: "total" });
}

document.getElementById("analytics-prev-month").addEventListener("click", () => {
  state.analyticsMonth.setMonth(state.analyticsMonth.getMonth() - 1);
  loadAnalytics();
});
document.getElementById("analytics-next-month").addEventListener("click", () => {
  state.analyticsMonth.setMonth(state.analyticsMonth.getMonth() + 1);
  loadAnalytics();
});

/* ============================================================
   GOALS
   ============================================================ */

async function loadGoals() {
  const goals = await Api.listGoals();
  const grid = document.getElementById("goals-grid");
  if (goals.length === 0) {
    grid.innerHTML = `<div class="empty-state">No savings goals yet — set one to see a projection.</div>`;
    return;
  }
  grid.innerHTML = goals
    .map(
      (g) => `
      <div class="stat-tile goal-card">
        <div class="flex-between">
          <strong>${g.name}</strong>
          <span class="pill ${g.on_track ? "pill-good" : "pill-warning"}">${g.on_track ? "On track" : "Behind"}</span>
        </div>
        <div class="goal-ring-row">
          <div id="ring-${g.id}"></div>
          <div>
            <div class="text-sm text-muted">Target</div>
            <div style="font-weight:700;">${formatMoney(g.target_amount)}</div>
            <div class="text-sm text-muted" style="margin-top:6px;">By ${g.deadline}</div>
          </div>
        </div>
        <div class="text-sm text-muted">
          Est. monthly savings: <strong>${formatMoney(g.estimated_monthly_savings)}</strong> ·
          ${g.months_remaining} month${g.months_remaining === 1 ? "" : "s"} left
        </div>
        <div class="row-actions">
          <button class="btn btn-danger btn-sm" data-del-goal="${g.id}">Delete</button>
        </div>
      </div>`
    )
    .join("");

  goals.forEach((g) => {
    renderProgressRing(document.getElementById(`ring-${g.id}`), g.percent_of_target, {
      statusClass: g.on_track ? "good" : "warning",
    });
  });

  grid.querySelectorAll("[data-del-goal]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("Delete this savings goal?")) return;
      try {
        await Api.deleteGoal(b.dataset.delGoal);
        loadGoals();
      } catch (err) {
        toast(formatApiError(err), "error");
      }
    })
  );
}

document.getElementById("btn-add-goal").addEventListener("click", () => {
  openModal(`
    <div class="modal-header"><h3>New savings goal</h3><button class="modal-close" id="modal-close">&times;</button></div>
    <form class="auth-form" id="goal-form">
      <div class="field">
        <label>Goal name</label>
        <input type="text" id="goal-name" required placeholder="e.g. New laptop" />
      </div>
      <div class="form-grid">
        <div class="field">
          <label>Target amount (₹)</label>
          <input type="number" min="0.01" step="0.01" id="goal-amount" required />
        </div>
        <div class="field">
          <label>Deadline</label>
          <input type="date" id="goal-deadline" required />
        </div>
      </div>
      <p class="text-sm text-muted">Progress is projected from your monthly income (Settings) minus your recent average spend — set your income first for a real number.</p>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost" id="modal-cancel">Cancel</button>
        <button type="submit" class="btn btn-primary">Create goal</button>
      </div>
    </form>
  `);
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-cancel").addEventListener("click", closeModal);
  document.getElementById("goal-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await Api.createGoal({
        name: document.getElementById("goal-name").value.trim(),
        target_amount: document.getElementById("goal-amount").value,
        deadline: document.getElementById("goal-deadline").value,
      });
      closeModal();
      toast("Goal created.", "success");
      loadGoals();
    } catch (err) {
      toast(formatApiError(err), "error");
    }
  });
});

/* ============================================================
   ADVISOR
   ============================================================ */

function appendAdvisorMessage(text, from) {
  const log = document.getElementById("advisor-log");
  const bubble = el(`
    <div class="advisor-msg ${from}">
      <div class="advisor-avatar">${from === "user" ? (state.user?.email?.[0] || "U").toUpperCase() : "SW"}</div>
      <div class="advisor-bubble"></div>
    </div>
  `);
  bubble.querySelector(".advisor-bubble").textContent = text;
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

async function sendAdvisorQuestion() {
  const input = document.getElementById("advisor-input");
  const question = input.value.trim();
  if (!question) return;
  appendAdvisorMessage(question, "user");
  input.value = "";
  appendAdvisorMessage("Thinking…", "bot");
  const log = document.getElementById("advisor-log");
  const placeholder = log.lastElementChild;
  try {
    const { answer } = await Api.askAdvisor(question);
    placeholder.querySelector(".advisor-bubble").textContent = answer;
  } catch (err) {
    placeholder.querySelector(".advisor-bubble").textContent = formatApiError(err);
  }
}
document.getElementById("btn-advisor-send").addEventListener("click", sendAdvisorQuestion);
document.getElementById("advisor-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendAdvisorQuestion();
});

/* ============================================================
   SETTINGS
   ============================================================ */

document.querySelector('[data-view="settings"]').addEventListener("click", () => {
  document.getElementById("settings-name").value = state.user.full_name || "";
  document.getElementById("settings-income").value = state.user.monthly_income || "";
});

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const payload = {
      full_name: document.getElementById("settings-name").value || null,
      monthly_income: document.getElementById("settings-income").value || null,
    };
    state.user = await Api.updateMe(payload);
    toast("Profile updated.", "success");
  } catch (err) {
    toast(formatApiError(err), "error");
  }
});

document.getElementById("btn-export-csv").addEventListener("click", async () => {
  try {
    await downloadWithAuth(Api.exportCsvUrl(), "spendwise-expenses.csv");
  } catch (err) {
    toast(formatApiError(err), "error");
  }
});
document.getElementById("btn-export-pdf").addEventListener("click", async () => {
  const now = new Date();
  try {
    await downloadWithAuth(
      Api.exportPdfUrl(now.getFullYear(), now.getMonth() + 1),
      `spendwise-report-${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}.pdf`
    );
  } catch (err) {
    toast(formatApiError(err), "error");
  }
});
