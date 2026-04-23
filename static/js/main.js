/**
 * Expense Tracker — Main JS
 * Handles: form submission, table rendering,
 *          filters/sort, delete, summary, stats, toasts.
 */

"use strict";

/* ── Constants ──────────────────────────────────────────────────────────── */
const API_BASE = "/expenses";

const CAT_BADGE_CLASS = {
  Food:          "bg-warning  text-dark",
  Transport:     "bg-info     text-dark",
  Housing:       "bg-primary",
  Entertainment: "bg-danger",
  Healthcare:    "bg-success",
  Shopping:      "bg-purple  text-white",
  Education:     "bg-secondary",
  Other:         "bg-dark",
};

/* ── DOM refs (cached on load) ──────────────────────────────────────────── */
const dom = {
  form:           document.getElementById("expense-form"),
  idemKey:        document.getElementById("idempotency-key"),
  amount:         document.getElementById("amount"),
  category:       document.getElementById("category"),
  description:    document.getElementById("description"),
  date:           document.getElementById("date"),
  submitBtn:      document.getElementById("submit-btn"),
  btnLabel:       document.getElementById("btn-label"),
  btnSpinner:     document.getElementById("btn-spinner"),
  formAlert:      document.getElementById("form-alert"),
  filterCat:      document.getElementById("filter-category"),
  sortOrder:      document.getElementById("sort-order"),
  refreshBtn:     document.getElementById("refresh-btn"),
  totalDisplay:   document.getElementById("total-display"),
  tableLoading:   document.getElementById("table-loading"),
  tbody:          document.getElementById("expense-tbody"),
  statTotal:      document.getElementById("stat-total"),
  statCount:      document.getElementById("stat-count"),
  statTopCat:     document.getElementById("stat-top-cat"),
  statLatest:     document.getElementById("stat-latest"),
  summaryList:    document.getElementById("summary-list"),
  toastContainer: document.getElementById("toast-container"),
};

/* ══════════════════════════════════════════════════════════════════════════
   UTILITIES
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Escape HTML to prevent XSS when injecting user content into innerHTML.
 */
function escHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Generate a v4 UUID using the Web Crypto API.
 */
function generateUUID() {
  return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, (c) =>
    (
      c ^
      (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))
    ).toString(16)
  );
}

/**
 * Return a Bootstrap badge string for a given category.
 */
function catBadge(cat) {
  const cls = CAT_BADGE_CLASS[cat] ?? "bg-secondary";
  return `<span class="badge badge-cat ${cls}">${escHtml(cat)}</span>`;
}

/**
 * Today's date as YYYY-MM-DD.
 */
function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

/* ══════════════════════════════════════════════════════════════════════════
   TOAST
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Show a self-dismissing toast notification.
 * @param {string} msg
 * @param {"success"|"danger"|"warning"|"info"|"secondary"} type
 */
function showToast(msg, type = "success") {
  const id = `toast-${Date.now()}`;
  const html = `
    <div id="${id}"
         class="toast align-items-center text-bg-${type} border-0 fade-in-up"
         role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">${escHtml(msg)}</div>
        <button type="button"
                class="btn-close btn-close-white me-2 m-auto"
                data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>`;
  dom.toastContainer.insertAdjacentHTML("beforeend", html);

  const el = document.getElementById(id);
  // Auto-remove after 4 s
  setTimeout(() => {
    el?.classList.add("hide");
    setTimeout(() => el?.remove(), 300);
  }, 4000);
}

/* ══════════════════════════════════════════════════════════════════════════
   FORM HELPERS
   ══════════════════════════════════════════════════════════════════════════ */

function setFormLoading(loading) {
  dom.submitBtn.disabled = loading;
  dom.btnLabel.classList.toggle("d-none", loading);
  dom.btnSpinner.classList.toggle("d-none", !loading);
}

function showFormAlert(msg, type = "danger") {
  dom.formAlert.className = `alert alert-${type} mt-3`;
  dom.formAlert.textContent = msg;
}

function hideFormAlert() {
  dom.formAlert.className = "alert mt-3 d-none";
  dom.formAlert.textContent = "";
}

function resetForm() {
  dom.form.reset();
  dom.form.classList.remove("was-validated");
  dom.date.value = todayISO();
  dom.idemKey.value = generateUUID();   // fresh key for next submission
  hideFormAlert();
}

/* ══════════════════════════════════════════════════════════════════════════
   API CALLS
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * POST a new expense to the backend.
 * Re-uses the same idempotency key on retries so the server de-duplicates.
 */
async function apiCreateExpense(payload) {
  const res  = await fetch(API_BASE, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? "Unexpected server error.");
  return { data, status: res.status };
}

/**
 * GET /expenses with optional category filter and sort.
 */
async function apiFetchExpenses(category = "", sort = "date_desc") {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (sort)     params.set("sort", sort);

  const res = await fetch(`${API_BASE}?${params.toString()}`);
  if (!res.ok) throw new Error(`Server responded with ${res.status}`);
  return res.json();
}

/**
 * GET /expenses/summary
 */
async function apiFetchSummary() {
  const res = await fetch(`${API_BASE}/summary`);
  if (!res.ok) throw new Error();
  return res.json();
}

/**
 * DELETE /expenses/:id
 */
async function apiDeleteExpense(id) {
  const res = await fetch(`${API_BASE}/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error ?? "Delete failed.");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   RENDER
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Render the expense rows into the table body.
 */
function renderTable(expenses) {
  dom.tbody.innerHTML = "";

  if (!expenses.length) {
    dom.tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center text-muted py-5">
          <i class="bi bi-inbox fs-3 d-block mb-2"></i>
          No expenses found.
        </td>
      </tr>`;
    return;
  }

  const fragment = document.createDocumentFragment();

  expenses.forEach((e, i) => {
    const tr = document.createElement("tr");
    tr.dataset.id = e.id;
    tr.classList.add("fade-in-up");
    tr.innerHTML = `
      <td class="text-muted small">${i + 1}</td>
      <td>${escHtml(e.date)}</td>
      <td>${catBadge(e.category)}</td>
      <td class="text-truncate" style="max-width:200px"
          title="${escHtml(e.description)}">
        ${escHtml(e.description) || '<span class="text-muted fst-italic">—</span>'}
      </td>
      <td class="text-end fw-semibold">${escHtml(e.amount_display)}</td>
      <td class="text-center">
        <button class="btn btn-sm btn-outline-danger delete-btn"
                data-id="${e.id}" aria-label="Delete expense ${e.id}">
          <i class="bi bi-trash3" aria-hidden="true"></i>
        </button>
      </td>`;
    fragment.appendChild(tr);
  });

  dom.tbody.appendChild(fragment);
}

/**
 * Render the category summary bars.
 */
function renderSummary(data) {
  if (!data.length) {
    dom.summaryList.innerHTML =
      '<p class="text-muted small mb-0">No data yet.</p>';
    dom.statTopCat.textContent = "—";
    return;
  }

  dom.statTopCat.textContent = data[0].category;
  const maxVal = parseFloat(data[0].total);

  dom.summaryList.innerHTML = data
    .map((d) => {
      const pct = maxVal > 0
        ? Math.round((parseFloat(d.total) / maxVal) * 100)
        : 0;
      return `
        <div class="mb-3">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span>${catBadge(d.category)}
              <span class="text-muted small ms-1">${d.count} entry${d.count !== 1 ? "ies" : "y"}</span>
            </span>
            <span class="fw-semibold small">${escHtml(d.total_display)}</span>
          </div>
          <div class="summary-track">
            <div class="summary-fill" style="width:${pct}%"></div>
          </div>
        </div>`;
    })
    .join("");
}

/**
 * Update the four stat cards at the top of the page.
 */
function updateStats(data) {
  dom.statTotal.textContent = data.total_display;
  dom.statCount.textContent = data.count;
  if (data.expenses.length) {
    const latest = data.expenses[0];
    dom.statLatest.textContent = `${latest.date} · ${latest.category}`;
  } else {
    dom.statLatest.textContent = "—";
  }
  dom.totalDisplay.textContent = data.total_display;
}

/* ══════════════════════════════════════════════════════════════════════════
   LOAD EXPENSES  (with auto-retry)
   ══════════════════════════════════════════════════════════════════════════ */

let _retryTimer = null;

async function loadExpenses() {
  clearTimeout(_retryTimer);
  dom.tableLoading.classList.remove("d-none");

  try {
    const data = await apiFetchExpenses(
      dom.filterCat.value,
      dom.sortOrder.value
    );
    renderTable(data.expenses);
    updateStats(data);

    // Load summary separately (non-critical)
    apiFetchSummary()
      .then(renderSummary)
      .catch(() => {}); // silent failure for summary

  } catch (err) {
    showToast("Failed to load expenses — retrying in 5 s…", "warning");
    _retryTimer = setTimeout(loadExpenses, 5000);
  } finally {
    dom.tableLoading.classList.add("d-none");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   EVENT LISTENERS
   ══════════════════════════════════════════════════════════════════════════ */

/* ── Form submit ─────────────────────────────────────────────────────────── */
dom.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideFormAlert();

  // HTML5 client-side validation gate
  if (!dom.form.checkValidity()) {
    dom.form.classList.add("was-validated");
    return;
  }

  const payload = {
    amount:          dom.amount.value,
    category:        dom.category.value,
    description:     dom.description.value,
    date:            dom.date.value,
    idempotency_key: dom.idemKey.value,
  };

  setFormLoading(true);

  try {
    const { data, status } = await apiCreateExpense(payload);

    if (status === 201) {
      showToast(`Expense added: ${data.amount_display}`, "success");
    } else {
      showToast("Already saved — duplicate request detected.", "info");
    }

    resetForm();
    loadExpenses();

  } catch (err) {
    // Network or server error — do NOT reset the idempotency key
    // so the user can safely retry and the server will deduplicate.
    showFormAlert(err.message ?? "Network error. Please try again.");
  } finally {
    setFormLoading(false);
  }
});

/* ── Delete (event delegation on tbody) ──────────────────────────────────── */
dom.tbody.addEventListener("click", async (e) => {
  const btn = e.target.closest(".delete-btn");
  if (!btn) return;

  if (!confirm("Delete this expense? This cannot be undone.")) return;

  const id = btn.dataset.id;
  btn.disabled = true;

  try {
    await apiDeleteExpense(id);
    showToast("Expense deleted.", "secondary");
    loadExpenses();
  } catch (err) {
    showToast(err.message ?? "Could not delete. Try again.", "danger");
    btn.disabled = false;
  }
});

/* ── Filters & sort ──────────────────────────────────────────────────────── */
dom.filterCat.addEventListener("change", loadExpenses);
dom.sortOrder.addEventListener("change", loadExpenses);
dom.refreshBtn.addEventListener("click", loadExpenses);

/* ══════════════════════════════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════════════════════════════ */

(function init() {
  // Set today's date as default
  dom.date.value = todayISO();
  // Generate first idempotency key
  dom.idemKey.value = generateUUID();
  // Load expenses on page ready
  loadExpenses();
})();