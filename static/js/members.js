"use strict";

let members = [];
const memberForm = document.querySelector("#memberForm");

async function loadMembers() {
  try {
    const search = encodeURIComponent(document.querySelector("#memberSearch").value);
    const result = await api(`/api/members?search=${search}`);
    members = result.data;
    document.querySelector("#memberRows").innerHTML = members.length
      ? members.map(member => `<tr><td>${escapeHtml(member.membership_number)}</td><td><strong>${escapeHtml(member.full_name)}</strong></td><td>${escapeHtml(member.email)}</td><td>${escapeHtml(member.phone)}</td><td>${escapeHtml(member.address || "—")}</td><td>${member.registration_date}</td><td>${statusBadge(member.status)}</td><td><button type="button" class="button small secondary" data-edit="${member.member_id}">Edit</button></td></tr>`).join("")
      : emptyRow(8, "No members found.");
  } catch (error) { showToast(error.message, "error"); }
}

function clearMemberForm(notify = false) {
  memberForm.reset();
  document.querySelector("#memberId").value = "";
  document.querySelector("#memberStatus").value = "Active";
  document.querySelector("#memberSubmit").textContent = "Save member";
  if (notify) showToast("Member form cleared.", "info");
}

memberForm.addEventListener("submit", async event => {
  event.preventDefault();
  const id = document.querySelector("#memberId").value;
  const submitButton = document.querySelector("#memberSubmit");
  const body = {
    full_name: document.querySelector("#memberName").value,
    email: document.querySelector("#memberEmail").value,
    phone: document.querySelector("#memberPhone").value,
    address: document.querySelector("#memberAddress").value,
    status: document.querySelector("#memberStatus").value,
  };
  setButtonBusy(submitButton, true, id ? "Updating…" : "Saving…");
  try {
    const result = await api(id ? `/api/members/${id}` : "/api/members", { method: id ? "PUT" : "POST", body });
    showToast(result.message);
    clearMemberForm();
    await loadMembers();
  } catch (error) { showToast(error.message, "error"); }
  finally { setButtonBusy(submitButton, false); }
});

document.querySelector("#memberRows").addEventListener("click", event => {
  const button = event.target.closest("button");
  const id = button?.dataset.edit;
  if (!id) return;
  const member = members.find(item => String(item.member_id) === id);
  if (!member) return;
  document.querySelector("#memberId").value = member.member_id;
  document.querySelector("#memberName").value = member.full_name;
  document.querySelector("#memberEmail").value = member.email;
  document.querySelector("#memberPhone").value = member.phone;
  document.querySelector("#memberAddress").value = member.address || "";
  document.querySelector("#memberStatus").value = member.status;
  document.querySelector("#memberSubmit").textContent = "Update member";
  window.scrollTo({ top: 0, behavior: "smooth" });
  showToast(`Editing ${member.full_name}.`, "info");
});

document.querySelector("#clearMember").addEventListener("click", () => clearMemberForm(true));
document.querySelector("#memberSearch").addEventListener("input", loadMembers);
loadMembers();
