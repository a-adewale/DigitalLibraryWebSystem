"""Flask web server for the Digital Library system.

HTML/CSS/JavaScript provide the frontend. Flask receives browser requests,
calls the database functions and returns either pages or JSON responses.
"""

from __future__ import annotations

import os
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import database
import paystack_service
from config import APP_TITLE, DAILY_FINE_NAIRA, LOAN_PERIOD_DAYS


paystack_service.load_environment()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-development-key")

database.initialise_database()

if os.getenv("SEED_DEMO_DATA", "0") == "1":
    database.seed_demo_data()


def login_required(function):
    """Redirect browser pages to login and reject unauthenticated API calls."""

    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "Please sign in."}), 401
            return redirect(url_for("login_page"))
        return function(*args, **kwargs)

    return wrapper


def json_success(data=None, message=""):
    return jsonify({"success": True, "message": message, "data": data})


def json_error(error, status=400):
    return jsonify({"success": False, "message": str(error)}), status


def required_int(payload: dict, field_name: str) -> int:
    """Read a required whole number from a JSON request."""
    value = payload.get(field_name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"{field_name.replace('_', ' ').title()} is required.")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name.replace('_', ' ').title()} must be a whole number."
        ) from error


@app.get("/")
def index():
    return redirect(url_for("dashboard_page" if "user" in session else "login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    error = None
    if request.method == "POST":
        user = database.authenticate_user(
            request.form.get("username", ""), request.form.get("password", "")
        )
        if user:
            session.clear()
            session["user"] = user
            return redirect(url_for("dashboard_page"))
        error = "The username or password is incorrect."
    return render_template("login.html", title="Sign in", error=error)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.get("/dashboard")
@login_required
def dashboard_page():
    return render_template(
        "dashboard.html",
        title="Dashboard",
        stats=database.get_dashboard_statistics(),
        recent_loans=database.get_recent_loans(),
    )


@app.get("/books")
@login_required
def books_page():
    return render_template("books.html", title="Books")


@app.get("/members")
@login_required
def members_page():
    return render_template("members.html", title="Members")


@app.get("/lending")
@login_required
def lending_page():
    return render_template(
        "lending.html",
        title="Borrow and Return",
        loan_period_days=LOAN_PERIOD_DAYS,
    )


@app.get("/history")
@login_required
def history_page():
    return render_template("history.html", title="Borrowing History")


@app.get("/overdue")
@login_required
def overdue_page():
    return render_template(
        "overdue.html", title="Overdue Tracking", daily_fine=DAILY_FINE_NAIRA
    )


@app.get("/payments")
@login_required
def payments_page():
    return render_template("payments.html", title="Fine Payments")


# ------------------------------ Books API ------------------------------


@app.get("/api/categories")
@login_required
def api_categories():
    return json_success([dict(row) for row in database.get_categories()])


@app.post("/api/categories")
@login_required
def api_add_category():
    payload = request.get_json(silent=True) or {}
    try:
        category_id = database.add_category(str(payload.get("category_name", "")))
        return json_success({"category_id": category_id}, "Category added.")
    except ValueError as error:
        return json_error(error)


@app.get("/api/books")
@login_required
def api_books():
    rows = database.list_books(request.args.get("search", ""))
    return json_success([dict(row) for row in rows])


def book_values(payload: dict) -> tuple[str, str, str, int, int | None, int]:
    """Validate and convert the JSON fields shared by add and update book."""
    year = payload.get("publication_year")
    publication_year = required_int(payload, "publication_year") if str(year or "").strip() else None
    return (
        str(payload.get("isbn", "")),
        str(payload.get("title", "")),
        str(payload.get("author", "")),
        required_int(payload, "category_id"),
        publication_year,
        required_int(payload, "total_copies"),
    )


@app.post("/api/books")
@login_required
def api_add_book():
    try:
        book_id = database.add_book(*book_values(request.get_json(silent=True) or {}))
        return json_success({"book_id": book_id}, "Book added."), 201
    except (ValueError, TypeError) as error:
        return json_error(error)


@app.put("/api/books/<int:book_id>")
@login_required
def api_update_book(book_id):
    try:
        database.update_book(
            book_id, *book_values(request.get_json(silent=True) or {})
        )
        return json_success(message="Book updated.")
    except (ValueError, TypeError) as error:
        return json_error(error)


@app.delete("/api/books/<int:book_id>")
@login_required
def api_delete_book(book_id):
    try:
        database.delete_book(book_id)
        return json_success(message="Book deleted.")
    except ValueError as error:
        return json_error(error)


# ----------------------------- Members API -----------------------------


@app.get("/api/members")
@login_required
def api_members():
    rows = database.list_members(request.args.get("search", ""))
    return json_success([dict(row) for row in rows])


@app.post("/api/members")
@login_required
def api_add_member():
    payload = request.get_json(silent=True) or {}
    try:
        member_id = database.add_member(
            payload.get("full_name", ""),
            payload.get("email", ""),
            payload.get("phone", ""),
            payload.get("address", ""),
        )
        return json_success({"member_id": member_id}, "Member registered."), 201
    except ValueError as error:
        return json_error(error)


@app.put("/api/members/<int:member_id>")
@login_required
def api_update_member(member_id):
    payload = request.get_json(silent=True) or {}
    try:
        database.update_member(
            member_id,
            payload.get("full_name", ""),
            payload.get("email", ""),
            payload.get("phone", ""),
            payload.get("address", ""),
            payload.get("status", "Active"),
        )
        return json_success(message="Member updated.")
    except ValueError as error:
        return json_error(error)


# ----------------------- Lending, history, overdue -----------------------


@app.get("/api/lending/options")
@login_required
def api_lending_options():
    return json_success(
        {
            "members": [dict(row) for row in database.get_active_members()],
            "books": [dict(row) for row in database.get_available_books()],
        }
    )


@app.get("/api/loans/active")
@login_required
def api_active_loans():
    return json_success([dict(row) for row in database.list_active_loans()])


@app.post("/api/loans")
@login_required
def api_borrow_book():
    payload = request.get_json(silent=True) or {}
    try:
        loan_id = database.borrow_book(
            required_int(payload, "book_id"),
            required_int(payload, "member_id"),
            payload.get("borrowed_date"),
            payload.get("due_date"),
        )
        return json_success({"loan_id": loan_id}, "Book issued."), 201
    except (ValueError, TypeError) as error:
        return json_error(error)


@app.post("/api/loans/<int:loan_id>/return")
@login_required
def api_return_book(loan_id):
    try:
        payload = request.get_json(silent=True) or {}
        result = database.return_book(loan_id, payload.get("returned_date"))
        return json_success(result, "Book returned.")
    except ValueError as error:
        return json_error(error)


@app.get("/api/history")
@login_required
def api_history():
    rows = database.list_loan_history(
        request.args.get("search", ""), request.args.get("status", "All")
    )
    return json_success([dict(row) for row in rows])


@app.get("/api/overdue")
@login_required
def api_overdue():
    return json_success(database.list_overdue_loans())


# ----------------------------- Payments API -----------------------------


@app.get("/api/payments")
@login_required
def api_payments():
    return json_success(
        {
            "outstanding": [dict(row) for row in database.list_outstanding_fines()],
            "history": [dict(row) for row in database.list_payments()],
        }
    )


@app.post("/api/payments/initialise")
@login_required
def api_initialise_payment():
    payload = request.get_json(silent=True) or {}
    try:
        loan_id = required_int(payload, "loan_id")
        fine = next(
            (row for row in database.list_outstanding_fines() if row["loan_id"] == loan_id),
            None,
        )
        if fine is None:
            raise ValueError("The selected fine is no longer outstanding.")
        reference = paystack_service.create_reference()
        transaction = paystack_service.initialise_transaction(
            fine["email"], fine["fine_amount"], reference
        )
        database.save_pending_payment(
            fine["loan_id"],
            fine["member_id"],
            fine["fine_amount"],
            transaction["reference"],
            transaction["authorization_url"],
        )
        return json_success(
            {
                "reference": transaction["reference"],
                "authorization_url": transaction["authorization_url"],
            },
            "Checkout created.",
        )
    except (ValueError, RuntimeError, KeyError, TypeError) as error:
        return json_error(error)


@app.post("/api/payments/<reference>/verify")
@login_required
def api_verify_payment(reference):
    payment = database.get_payment(reference)
    if payment is None:
        return json_error("Payment record not found.", 404)
    try:
        result = paystack_service.verify_transaction(reference, payment["amount"])
        if result["successful"]:
            database.update_payment_status(reference, "Successful")
            return json_success(result, "Payment verified.")
        return json_error(f"Payment status: {result['gateway_status']}.")
    except (ValueError, RuntimeError) as error:
        return json_error(error)


@app.context_processor
def global_template_values():
    return {"app_title": APP_TITLE, "logged_in_user": session.get("user")}


if __name__ == "__main__":
    database.initialise_database()
    app.run(debug=True)
