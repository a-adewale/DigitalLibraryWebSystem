"use strict";

async function loadOverdue(notify = false) {
  try {
    const result = await api("/api/overdue");
    document.querySelector("#overdueRows").innerHTML = result.data.length
      ? result.data.map(loan => `<tr><td>#${loan.loan_id}</td><td><strong>${escapeHtml(loan.full_name)}</strong></td><td>${escapeHtml(loan.email)}</td><td>${escapeHtml(loan.phone)}</td><td>${escapeHtml(loan.title)}</td><td>${loan.due_date}</td><td><span class="late-days">${loan.overdue_days}</span></td><td><strong>${money(loan.current_fine)}</strong></td></tr>`).join("")
      : emptyRow(8, "There are no overdue loans.");
    if (notify) showToast("Overdue records refreshed.", "info");
  } catch (error) { showToast(error.message, "error"); }
}
document.querySelector("#refreshOverdue").addEventListener("click", () => loadOverdue(true));
loadOverdue();
