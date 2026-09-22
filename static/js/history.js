"use strict";

let historyRows = [];
async function loadHistory() {
  try {
    const search = encodeURIComponent(document.querySelector("#historySearch").value);
    const status = encodeURIComponent(document.querySelector("#historyStatus").value);
    const result = await api(`/api/history?search=${search}&status=${status}`);
    historyRows = result.data;
    document.querySelector("#historyRows").innerHTML = historyRows.length
      ? historyRows.map(loan => `<tr><td>#${loan.loan_id}</td><td>${escapeHtml(loan.membership_number)}</td><td><strong>${escapeHtml(loan.full_name)}</strong></td><td>${escapeHtml(loan.title)}</td><td>${loan.borrowed_date}</td><td>${loan.due_date}</td><td>${loan.returned_date || "—"}</td><td>${statusBadge(loan.status)}</td><td>${money(loan.fine_amount)}</td></tr>`).join("")
      : emptyRow(9, "No borrowing records found.");
  } catch (error) { showToast(error.message, "error"); }
}

function csvValue(value) { return `"${String(value ?? "").replaceAll('"', '""')}"`; }
document.querySelector("#exportHistory").addEventListener("click", () => {
  if (!historyRows.length) {
    showToast("There are no records to export.", "warning");
    return;
  }
  const columns = ["Loan", "Membership Number", "Member", "Book", "Borrowed", "Due", "Returned", "Status", "Fine"];
  const lines = [columns, ...historyRows.map(row => [row.loan_id, row.membership_number, row.full_name, row.title, row.borrowed_date, row.due_date, row.returned_date || "", row.status, row.fine_amount])];
  const blob = new Blob([lines.map(row => row.map(csvValue).join(",")).join("\n")], { type: "text/csv" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "borrowing_history.csv";
  link.click();
  URL.revokeObjectURL(link.href);
  showToast("Borrowing history exported.");
});
document.querySelector("#historySearch").addEventListener("input", loadHistory);
document.querySelector("#historyStatus").addEventListener("change", loadHistory);
loadHistory();
