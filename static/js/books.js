"use strict";

let books = [];
const bookForm = document.querySelector("#bookForm");

async function loadCategories(selected = "") {
  const result = await api("/api/categories");
  document.querySelector("#category").innerHTML = result.data
    .map(item => `<option value="${item.category_id}" ${String(item.category_id) === String(selected) ? "selected" : ""}>${escapeHtml(item.category_name)}</option>`)
    .join("");
}

async function loadBooks() {
  try {
    const search = encodeURIComponent(document.querySelector("#bookSearch").value);
    const result = await api(`/api/books?search=${search}`);
    books = result.data;
    document.querySelector("#bookRows").innerHTML = books.length
      ? books.map(book => `<tr><td>${escapeHtml(book.isbn)}</td><td><strong>${escapeHtml(book.title)}</strong></td><td>${escapeHtml(book.author)}</td><td>${escapeHtml(book.category_name)}</td><td>${book.publication_year || "—"}</td><td>${book.total_copies}</td><td>${book.available_copies}</td><td class="table-actions"><button type="button" class="button small secondary" data-edit="${book.book_id}">Edit</button><button type="button" class="button small danger ghost" data-delete="${book.book_id}">Delete</button></td></tr>`).join("")
      : emptyRow(8, "No books found.");
  } catch (error) { showToast(error.message, "error"); }
}

function clearBookForm(notify = false) {
  bookForm.reset();
  document.querySelector("#bookId").value = "";
  document.querySelector("#copies").value = 1;
  document.querySelector("#bookSubmit").textContent = "Save book";
  if (notify) showToast("Book form cleared.", "info");
}

bookForm.addEventListener("submit", async event => {
  event.preventDefault();
  const submitButton = document.querySelector("#bookSubmit");
  const id = document.querySelector("#bookId").value;
  const body = {
    isbn: document.querySelector("#isbn").value,
    title: document.querySelector("#bookTitle").value,
    author: document.querySelector("#author").value,
    category_id: document.querySelector("#category").value,
    publication_year: document.querySelector("#year").value,
    total_copies: document.querySelector("#copies").value,
  };
  setButtonBusy(submitButton, true, id ? "Updating…" : "Saving…");
  try {
    const result = await api(id ? `/api/books/${id}` : "/api/books", { method: id ? "PUT" : "POST", body });
    showToast(result.message);
    clearBookForm();
    await loadBooks();
  } catch (error) { showToast(error.message, "error"); }
  finally { setButtonBusy(submitButton, false); }
});

document.querySelector("#bookRows").addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  const editId = button.dataset.edit;
  const deleteId = button.dataset.delete;
  if (editId) {
    const book = books.find(item => String(item.book_id) === editId);
    if (!book) return;
    document.querySelector("#bookId").value = book.book_id;
    document.querySelector("#isbn").value = book.isbn;
    document.querySelector("#bookTitle").value = book.title;
    document.querySelector("#author").value = book.author;
    document.querySelector("#year").value = book.publication_year || "";
    document.querySelector("#copies").value = book.total_copies;
    document.querySelector("#bookSubmit").textContent = "Update book";
    const categories = await api("/api/categories");
    const selected = categories.data.find(item => item.category_name === book.category_name);
    await loadCategories(selected?.category_id);
    window.scrollTo({ top: 0, behavior: "smooth" });
    showToast(`Editing “${book.title}”.`, "info");
  }
  if (deleteId) {
    const book = books.find(item => String(item.book_id) === deleteId);
    const confirmed = await confirmAction({
      title: "Delete book?",
      message: `This will permanently remove “${book?.title || "this book"}” from the catalogue.`,
      type: "danger", confirmText: "Delete book",
    });
    if (!confirmed) return;
    setButtonBusy(button, true, "Deleting…");
    try {
      const result = await api(`/api/books/${deleteId}`, { method: "DELETE" });
      showToast(result.message);
      await loadBooks();
    } catch (error) {
      showToast(error.message, "error");
      setButtonBusy(button, false);
    }
  }
});

document.querySelector("#addCategory").addEventListener("click", async () => {
  const categoryName = await promptValue({
    title: "Add a book category",
    message: "Enter a category name. It will immediately appear in the category list.",
    inputLabel: "Category name", inputPlaceholder: "For example: Poetry",
    required: true, confirmText: "Add category",
  });
  if (categoryName === null) return;
  try {
    const result = await api("/api/categories", { method: "POST", body: { category_name: categoryName } });
    await loadCategories(result.data.category_id);
    showToast(result.message);
  } catch (error) { showToast(error.message, "error"); }
});

document.querySelector("#clearBook").addEventListener("click", () => clearBookForm(true));
document.querySelector("#bookSearch").addEventListener("input", loadBooks);
loadCategories().then(loadBooks).catch(error => showToast(error.message, "error"));
