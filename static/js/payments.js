"use strict";

async function loadPayments(notify = false) {
  try {
    const result = await api("/api/payments");
    document.querySelector("#fineRows").innerHTML = result.data.outstanding.length
      ? result.data.outstanding.map(fine => `<tr><td>#${fine.loan_id}</td><td><strong>${escapeHtml(fine.full_name)}</strong></td><td>${escapeHtml(fine.email)}</td><td>${escapeHtml(fine.title)}</td><td>${fine.returned_date || "—"}</td><td><strong>${money(fine.fine_amount)}</strong></td><td>${statusBadge(fine.payment_status)}</td><td><button type="button" class="button small primary" data-pay="${fine.loan_id}" data-amount="${fine.fine_amount}">Pay with Paystack</button></td></tr>`).join("")
      : emptyRow(8, "No outstanding fines.");
    document.querySelector("#paymentRows").innerHTML = result.data.history.length
      ? result.data.history.map(payment => `<tr><td class="reference">${escapeHtml(payment.payment_reference)}</td><td>${escapeHtml(payment.full_name)}</td><td>${escapeHtml(payment.title)}</td><td>${money(payment.amount)}</td><td>${statusBadge(payment.payment_status)}</td><td>${payment.payment_date || "—"}</td><td>${payment.payment_status === "Pending" ? `<button type="button" class="button small secondary" data-verify="${escapeHtml(payment.payment_reference)}">Verify</button>` : "—"}</td></tr>`).join("")
      : emptyRow(7, "No payment records.");
    if (notify) showToast("Payment records refreshed.", "info");
  } catch (error) { showToast(error.message, "error"); }
}

document.querySelector("#fineRows").addEventListener("click", async event => {
  const button = event.target.closest("button");
  const loanId = button?.dataset.pay;
  if (!loanId) return;
  const confirmed = await confirmAction({
    title: "Open Paystack checkout?",
    message: `A Paystack test checkout will open for ${money(button.dataset.amount)}. No real money is charged in test mode.`,
    confirmText: "Continue to Paystack",
  });
  if (!confirmed) return;

  const checkoutWindow = window.open("about:blank", "_blank");
  setButtonBusy(button, true, "Opening…");
  try {
    const result = await api("/api/payments/initialise", { method: "POST", body: { loan_id: loanId } });
    if (checkoutWindow) {
      checkoutWindow.opener = null;
      checkoutWindow.location.href = result.data.authorization_url;
    } else {
      window.location.href = result.data.authorization_url;
    }
    showToast("Paystack checkout opened. Complete payment, then return and click Verify.", "info");
    await loadPayments();
  } catch (error) {
    if (checkoutWindow) checkoutWindow.close();
    showToast(error.message, "error");
    setButtonBusy(button, false);
  }
});

document.querySelector("#paymentRows").addEventListener("click", async event => {
  const button = event.target.closest("button");
  const reference = button?.dataset.verify;
  if (!reference) return;
  setButtonBusy(button, true, "Checking…");
  try {
    const result = await api(`/api/payments/${encodeURIComponent(reference)}/verify`, { method: "POST" });
    showToast(result.message);
    await loadPayments();
  } catch (error) {
    showToast(error.message, "error");
    setButtonBusy(button, false);
  }
});

document.querySelector("#refreshPayments").addEventListener("click", () => loadPayments(true));
loadPayments();
