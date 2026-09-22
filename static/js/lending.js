"use strict";

function isoDate(value) { return value.toISOString().slice(0, 10); }
function setLoanDates() {
  const borrowed = new Date();
  const due = new Date();
  due.setDate(due.getDate() + window.LOAN_PERIOD_DAYS);
  document.querySelector("#borrowedDate").value = isoDate(borrowed);
  document.querySelector("#dueDate").value = isoDate(due);
}

async function loadOptions() {
  const result = await api("/api/lending/options");
  document.querySelector("#loanMember").innerHTML = `<option value="">Select member</option>${result.data.members.map(member => `<option value="${member.member_id}">${escapeHtml(member.membership_number)} — ${escapeHtml(member.full_name)}</option>`).join("")}`;
  document.querySelector("#loanBook").innerHTML = `<option value="">Select book</option>${result.data.books.map(book => `<option value="${book.book_id}">${escapeHtml(book.title)} by ${escapeHtml(book.author)} (${book.available_copies} available)</option>`).join("")}`;
}

async function loadLoans(notify = false) {
  try {
    const result = await api("/api/loans/active");
    document.querySelector("#loanRows").innerHTML = result.data.length
      ? result.data.map(loan => `<tr><td>#${loan.loan_id}</td><td>${escapeHtml(loan.membership_number)}</td><td><strong>${escapeHtml(loan.full_name)}</strong></td><td>${escapeHtml(loan.title)}</td><td>${loan.borrowed_date}</td><td>${loan.due_date}</td><td>${statusBadge(loan.status)}</td><td><button type="button" class="button small primary" data-return="${loan.loan_id}" data-title="${escapeHtml(loan.title)}">Return</button></td></tr>`).join("")
      : emptyRow(8, "No active loans.");
    if (notify) showToast("Current loans refreshed.", "info");
  } catch (error) { showToast(error.message, "error"); }
}

document.querySelector("#borrowedDate").addEventListener("change", event => {
  if (!event.target.value) return;
  const due = new Date(`${event.target.value}T00:00:00`);
  due.setDate(due.getDate() + window.LOAN_PERIOD_DAYS);
  document.querySelector("#dueDate").value = isoDate(due);
});

document.querySelector("#loanForm").addEventListener("submit", async event => {
  event.preventDefault();
  const submitButton = document.querySelector("#loanSubmit");
  const body = {
    member_id: document.querySelector("#loanMember").value,
    book_id: document.querySelector("#loanBook").value,
    borrowed_date: document.querySelector("#borrowedDate").value,
    due_date: document.querySelector("#dueDate").value,
  };
  setButtonBusy(submitButton, true, "Issuing…");
  try {
    const result = await api("/api/loans", { method: "POST", body });
    showToast(result.message);
    await Promise.all([loadOptions(), loadLoans()]);
  } catch (error) { showToast(error.message, "error"); }
  finally { setButtonBusy(submitButton, false); }
});

document.querySelector("#loanRows").addEventListener("click", async event => {
  const button = event.target.closest("button");
  const id = button?.dataset.return;
  if (!id) return;
  const returnedDate = await promptValue({
    title: "Return this book",
    message: `Choose the return date for “${button.dataset.title || "this book"}”. Any late fine will be calculated automatically.`,
    inputLabel: "Return date", inputType: "date", inputValue: isoDate(new Date()),
    required: true, confirmText: "Confirm return",
  });
  if (returnedDate === null) return;
  setButtonBusy(button, true, "Returning…");
  try {
    const result = await api(`/api/loans/${id}/return`, { method: "POST", body: { returned_date: returnedDate } });
    showToast(`${result.message} Fine: ${money(result.data.fine_amount)}`);
    await Promise.all([loadOptions(), loadLoans()]);
  } catch (error) {
    showToast(error.message, "error");
    setButtonBusy(button, false);
  }
});

document.querySelector("#refreshLoans").addEventListener("click", () => loadLoans(true));
setLoanDates();
Promise.all([loadOptions(), loadLoans()]).catch(error => showToast(error.message, "error"));
