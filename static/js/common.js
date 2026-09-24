"use strict";

async function api(url, options = {}) {
  const settings = { ...options, headers: { ...(options.headers || {}) } };
  if (settings.body && typeof settings.body !== "string") {
    settings.headers["Content-Type"] = "application/json";
    settings.body = JSON.stringify(settings.body);
  }

  let response;
  try {
    response = await fetch(url, settings);
  } catch (error) {
    throw new Error("Cannot connect to the server. Check that Flask is running.");
  }
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("Please sign in.");
  }

  let result;
  try {
    result = await response.json();
  } catch (error) {
    throw new Error("The server returned an unreadable response.");
  }
  if (!response.ok || !result.success) {
    throw new Error(result.message || "Request failed.");
  }
  return result;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function money(value) {
  return new Intl.NumberFormat("en-NG", {
    style: "currency", currency: "NGN", maximumFractionDigits: 0,
  }).format(value || 0);
}

function showToast(message, type = "success") {
  const container = document.querySelector("#toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  const icons = { success: "✓", error: "!", info: "i", warning: "!" };
  toast.className = `toast ${type}`;
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.innerHTML = `<span class="toast-icon">${icons[type] || "i"}</span><span>${escapeHtml(message)}</span><button type="button" aria-label="Dismiss notification">×</button>`;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  const removeToast = () => {
    toast.classList.remove("show");
    window.setTimeout(() => toast.remove(), 220);
  };
  toast.querySelector("button").addEventListener("click", removeToast);
  window.setTimeout(removeToast, 4200);
}

function showModal(options = {}) {
  const modal = document.querySelector("#appModal");
  const title = document.querySelector("#modalTitle");
  const message = document.querySelector("#modalMessage");
  const icon = document.querySelector("#modalIcon");
  const inputWrap = document.querySelector("#modalInputWrap");
  const inputLabel = document.querySelector("#modalInputLabel");
  const input = document.querySelector("#modalInput");
  const cancel = document.querySelector("#modalCancel");
  const confirm = document.querySelector("#modalConfirm");
  const close = document.querySelector("#modalClose");
  const type = options.type || "confirm";

  title.textContent = options.title || "Confirm action";
  message.textContent = options.message || "";
  icon.textContent = type === "danger" ? "!" : type === "success" ? "✓" : "?";
  icon.className = `modal-icon ${type}`;
  confirm.textContent = options.confirmText || "Continue";
  confirm.className = `button ${type === "danger" ? "danger" : "primary"}`;
  cancel.textContent = options.cancelText || "Cancel";
  cancel.hidden = options.showCancel === false;

  const hasInput = Boolean(options.inputType);
  inputWrap.hidden = !hasInput;
  inputLabel.textContent = options.inputLabel || "Value";
  input.type = options.inputType || "text";
  input.value = options.inputValue || "";
  input.placeholder = options.inputPlaceholder || "";
  input.required = Boolean(options.required);

  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  window.setTimeout(() => (hasInput ? input : confirm).focus(), 30);

  return new Promise(resolve => {
    function finish(confirmed) {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      document.body.classList.remove("modal-open");
      confirm.removeEventListener("click", onConfirm);
      cancel.removeEventListener("click", onCancel);
      close.removeEventListener("click", onCancel);
      modal.removeEventListener("click", onBackdrop);
      document.removeEventListener("keydown", onKeydown);
      resolve({ confirmed, value: input.value.trim() });
    }
    function onConfirm() {
      if (hasInput && options.required && !input.value.trim()) {
        input.focus();
        input.classList.add("invalid");
        showToast(`${inputLabel.textContent} is required.`, "warning");
        return;
      }
      finish(true);
    }
    function onCancel() { finish(false); }
    function onBackdrop(event) { if (event.target === modal) finish(false); }
    function onKeydown(event) {
      if (event.key === "Escape") finish(false);
      if (event.key === "Enter" && hasInput) onConfirm();
    }
    input.classList.remove("invalid");
    confirm.addEventListener("click", onConfirm);
    cancel.addEventListener("click", onCancel);
    close.addEventListener("click", onCancel);
    modal.addEventListener("click", onBackdrop);
    document.addEventListener("keydown", onKeydown);
  });
}

async function confirmAction(options) {
  return (await showModal(options)).confirmed;
}

async function promptValue(options) {
  const result = await showModal({ ...options, inputType: options.inputType || "text" });
  return result.confirmed ? result.value : null;
}

function setButtonBusy(button, busy, busyText = "Working…") {
  if (!button) return;
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
    button.classList.add("busy");
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
    button.classList.remove("busy");
  }
}

function statusBadge(status) {
  const safe = escapeHtml(status);
  return `<span class="status ${safe.toLowerCase().replaceAll(" ", "-")}">${safe}</span>`;
}

function emptyRow(columns, message) {
  return `<tr><td colspan="${columns}" class="empty">${escapeHtml(message)}</td></tr>`;
}

const currentPage = document.body.dataset.page;
const activeLink = document.querySelector(`[data-nav="${currentPage}"]`);
if (activeLink) {
  activeLink.classList.add("active");
  activeLink.setAttribute("aria-current", "page");
}

const mobileMenuToggle = document.querySelector("#mobileMenuToggle");
const mobileMenuClose = document.querySelector("#mobileMenuClose");
const sidebarOverlay = document.querySelector("#sidebarOverlay");

function setMobileMenu(open) {
  if (!mobileMenuToggle) return;
  document.body.classList.toggle("nav-open", open);
  mobileMenuToggle.setAttribute("aria-expanded", String(open));
  mobileMenuToggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  sidebarOverlay?.setAttribute("aria-hidden", String(!open));
  if (open) mobileMenuClose?.focus();
}

mobileMenuToggle?.addEventListener("click", () => {
  setMobileMenu(!document.body.classList.contains("nav-open"));
});
mobileMenuClose?.addEventListener("click", () => setMobileMenu(false));
sidebarOverlay?.addEventListener("click", () => setMobileMenu(false));
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && document.body.classList.contains("nav-open")) {
    setMobileMenu(false);
    mobileMenuToggle?.focus();
  }
});
window.addEventListener("resize", () => {
  if (window.innerWidth > 900 && document.body.classList.contains("nav-open")) {
    setMobileMenu(false);
  }
});
