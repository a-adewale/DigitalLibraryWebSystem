"""SQLite database operations for the Digital Library application.

The project intentionally uses Python's built-in sqlite3 module. Every SQL
statement is visible, which makes the code suitable for learning and defence.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from config import DAILY_FINE_NAIRA, DATABASE_PATH, LOAN_PERIOD_DAYS


def inserted_id(cursor: sqlite3.Cursor) -> int:
    """Return SQLite's new row ID, or fail clearly if none was created."""
    if cursor.lastrowid is None:
        raise RuntimeError("The database did not return an ID for the new record.")
    return cursor.lastrowid


def get_connection() -> sqlite3.Connection:
    """Open SQLite and return rows that support column-name access."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    """Create a random salt and a PBKDF2 password hash."""
    salt = salt or os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 100_000
    )
    return salt.hex(), password_hash.hex()


def verify_password(password: str, stored_salt: str, stored_hash: str) -> bool:
    """Return True when a plain password matches the stored hash."""
    salt = bytes.fromhex(stored_salt)
    _, calculated_hash = hash_password(password, salt)
    return hmac.compare_digest(calculated_hash, stored_hash)


def initialise_database() -> None:
    """Create all project tables and insert the initial administrator."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Librarian',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS books (
                book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                publication_year INTEGER,
                total_copies INTEGER NOT NULL CHECK(total_copies > 0),
                available_copies INTEGER NOT NULL
                    CHECK(available_copies >= 0 AND available_copies <= total_copies),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            );

            CREATE TABLE IF NOT EXISTS members (
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                membership_number TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                address TEXT,
                registration_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active'
                    CHECK(status IN ('Active', 'Inactive'))
            );

            CREATE TABLE IF NOT EXISTS loans (
                loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                borrowed_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                returned_date TEXT,
                status TEXT NOT NULL DEFAULT 'Borrowed'
                    CHECK(status IN ('Borrowed', 'Overdue', 'Returned')),
                fine_amount INTEGER NOT NULL DEFAULT 0 CHECK(fine_amount >= 0),
                FOREIGN KEY (book_id) REFERENCES books(book_id),
                FOREIGN KEY (member_id) REFERENCES members(member_id)
            );

            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                amount INTEGER NOT NULL CHECK(amount >= 0),
                payment_reference TEXT NOT NULL UNIQUE,
                payment_method TEXT NOT NULL DEFAULT 'Paystack',
                payment_status TEXT NOT NULL DEFAULT 'Pending'
                    CHECK(payment_status IN ('Pending', 'Successful', 'Failed')),
                authorization_url TEXT,
                payment_date TEXT,
                FOREIGN KEY (loan_id) REFERENCES loans(loan_id),
                FOREIGN KEY (member_id) REFERENCES members(member_id)
            );

            CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
            CREATE INDEX IF NOT EXISTS idx_members_name ON members(full_name);
            CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status);
            CREATE INDEX IF NOT EXISTS idx_payments_reference
                ON payments(payment_reference);
            """
        )

        for category in (
            "Fiction",
            "Non-fiction",
            "Science",
            "Technology",
            "Business",
            "History",
            "Biography",
            "Children",
            "Education",
            "Other",
        ):
            connection.execute(
                "INSERT OR IGNORE INTO categories(category_name) VALUES (?)",
                (category,),
            )

        existing_admin = connection.execute(
            "SELECT user_id FROM users WHERE username = ?", ("admin",)
        ).fetchone()
        if existing_admin is None:
            salt, password_hash = hash_password("admin123")
            connection.execute(
                """
                INSERT INTO users
                    (username, password_salt, password_hash, full_name, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "admin",
                    salt,
                    password_hash,
                    "System Administrator",
                    "Librarian",
                ),
            )


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Return basic user information when login details are correct."""
    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT user_id, username, password_salt, password_hash,
                   full_name, role
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (username.strip(),),
        ).fetchone()

    if user is None or not verify_password(
        password, user["password_salt"], user["password_hash"]
    ):
        return None

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
    }


# ------------------------- Categories and books -------------------------


def get_categories() -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT category_id, category_name FROM categories ORDER BY category_name"
        ).fetchall()


def add_category(category_name: str) -> int:
    name = category_name.strip()
    if not name:
        raise ValueError("Category name is required.")
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO categories(category_name) VALUES (?)", (name,)
            )
            return inserted_id(cursor)
    except sqlite3.IntegrityError as error:
        raise ValueError("That category already exists.") from error


def list_books(search_text: str = "") -> list[sqlite3.Row]:
    search = f"%{search_text.strip()}%"
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT b.book_id, b.isbn, b.title, b.author,
                   c.category_name, b.publication_year,
                   b.total_copies, b.available_copies
            FROM books b
            JOIN categories c ON c.category_id = b.category_id
            WHERE b.isbn LIKE ? OR b.title LIKE ? OR b.author LIKE ?
                  OR c.category_name LIKE ?
            ORDER BY b.title, b.author
            """,
            (search, search, search, search),
        ).fetchall()


def add_book(
    isbn: str,
    title: str,
    author: str,
    category_id: int,
    publication_year: Optional[int],
    total_copies: int,
) -> int:
    isbn, title, author = isbn.strip(), title.strip(), author.strip()
    if not isbn or not title or not author:
        raise ValueError("ISBN, title and author are required.")
    if total_copies < 1:
        raise ValueError("Total copies must be at least 1.")
    current_year = date.today().year
    if publication_year and not 1000 <= publication_year <= current_year:
        raise ValueError(f"Publication year must be between 1000 and {current_year}.")
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO books
                    (isbn, title, author, category_id, publication_year,
                     total_copies, available_copies)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    isbn,
                    title,
                    author,
                    category_id,
                    publication_year,
                    total_copies,
                    total_copies,
                ),
            )
            return inserted_id(cursor)
    except sqlite3.IntegrityError as error:
        raise ValueError("The ISBN already exists or the category is invalid.") from error


def update_book(
    book_id: int,
    isbn: str,
    title: str,
    author: str,
    category_id: int,
    publication_year: Optional[int],
    total_copies: int,
) -> None:
    isbn, title, author = isbn.strip(), title.strip(), author.strip()
    if not isbn or not title or not author:
        raise ValueError("ISBN, title and author are required.")
    if total_copies < 1:
        raise ValueError("Total copies must be at least 1.")
    current_year = date.today().year
    if publication_year and not 1000 <= publication_year <= current_year:
        raise ValueError(f"Publication year must be between 1000 and {current_year}.")

    with get_connection() as connection:
        current = connection.execute(
            "SELECT total_copies, available_copies FROM books WHERE book_id = ?",
            (book_id,),
        ).fetchone()
        if current is None:
            raise ValueError("Book not found.")
        borrowed_copies = current["total_copies"] - current["available_copies"]
        if total_copies < borrowed_copies:
            raise ValueError(
                f"At least {borrowed_copies} copies are currently borrowed. "
                "Total copies cannot be lower than that."
            )
        available_copies = total_copies - borrowed_copies
        try:
            connection.execute(
                """
                UPDATE books
                SET isbn = ?, title = ?, author = ?, category_id = ?,
                    publication_year = ?, total_copies = ?, available_copies = ?
                WHERE book_id = ?
                """,
                (
                    isbn,
                    title,
                    author,
                    category_id,
                    publication_year,
                    total_copies,
                    available_copies,
                    book_id,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("The ISBN already belongs to another book.") from error


def delete_book(book_id: int) -> None:
    with get_connection() as connection:
        book = connection.execute(
            "SELECT book_id FROM books WHERE book_id = ?", (book_id,)
        ).fetchone()
        if book is None:
            raise ValueError("Book not found.")
        loan_count = connection.execute(
            "SELECT COUNT(*) AS count FROM loans WHERE book_id = ?", (book_id,)
        ).fetchone()["count"]
        if loan_count:
            raise ValueError("A book with borrowing history cannot be deleted.")
        connection.execute("DELETE FROM books WHERE book_id = ?", (book_id,))


def get_available_books() -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT book_id, title, author, available_copies
            FROM books
            WHERE available_copies > 0
            ORDER BY title
            """
        ).fetchall()


# ----------------------------- Members -----------------------------


def generate_membership_number() -> str:
    year = date.today().year
    with get_connection() as connection:
        next_number = connection.execute(
            "SELECT COALESCE(MAX(member_id), 0) + 1 AS next_number FROM members"
        ).fetchone()["next_number"]
    return f"LIB-{year}-{next_number:04d}"


def list_members(search_text: str = "") -> list[sqlite3.Row]:
    search = f"%{search_text.strip()}%"
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT member_id, membership_number, full_name, email, phone,
                   address, registration_date, status
            FROM members
            WHERE membership_number LIKE ? OR full_name LIKE ?
                  OR email LIKE ? OR phone LIKE ?
            ORDER BY full_name
            """,
            (search, search, search, search),
        ).fetchall()


def add_member(
    full_name: str,
    email: str,
    phone: str,
    address: str,
    membership_number: Optional[str] = None,
) -> int:
    full_name, email, phone = full_name.strip(), email.strip().lower(), phone.strip()
    if not full_name or not email or not phone:
        raise ValueError("Name, email and phone are required.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Enter a valid email address.")
    membership_number = membership_number or generate_membership_number()
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO members
                    (membership_number, full_name, email, phone, address,
                     registration_date, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Active')
                """,
                (
                    membership_number,
                    full_name,
                    email,
                    phone,
                    address.strip(),
                    date.today().isoformat(),
                ),
            )
            return inserted_id(cursor)
    except sqlite3.IntegrityError as error:
        raise ValueError("The membership number or email already exists.") from error


def update_member(
    member_id: int,
    full_name: str,
    email: str,
    phone: str,
    address: str,
    status: str,
) -> None:
    full_name, email, phone = full_name.strip(), email.strip().lower(), phone.strip()
    if not full_name or not email or not phone:
        raise ValueError("Name, email and phone are required.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Enter a valid email address.")
    if status not in ("Active", "Inactive"):
        raise ValueError("Member status is invalid.")
    if status == "Inactive":
        with get_connection() as connection:
            active_loans = connection.execute(
                """
                SELECT COUNT(*) AS count FROM loans
                WHERE member_id = ? AND returned_date IS NULL
                """,
                (member_id,),
            ).fetchone()["count"]
        if active_loans:
            raise ValueError("Return all borrowed books before deactivating the member.")
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE members
                SET full_name = ?, email = ?, phone = ?, address = ?, status = ?
                WHERE member_id = ?
                """,
                (full_name, email, phone, address.strip(), status, member_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Member not found.")
    except sqlite3.IntegrityError as error:
        raise ValueError("That email already belongs to another member.") from error


def get_active_members() -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT member_id, membership_number, full_name, email
            FROM members
            WHERE status = 'Active'
            ORDER BY full_name
            """
        ).fetchall()


# ------------------------- Borrowing and returns -------------------------


def borrow_book(
    book_id: int,
    member_id: int,
    borrowed_date: Optional[str] = None,
    due_date: Optional[str] = None,
) -> int:
    borrowed = date.fromisoformat(borrowed_date) if borrowed_date else date.today()
    due = date.fromisoformat(due_date) if due_date else borrowed + timedelta(
        days=LOAN_PERIOD_DAYS
    )
    if due < borrowed:
        raise ValueError("Due date cannot be earlier than the borrowing date.")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        book = connection.execute(
            "SELECT available_copies FROM books WHERE book_id = ?", (book_id,)
        ).fetchone()
        member = connection.execute(
            "SELECT status FROM members WHERE member_id = ?", (member_id,)
        ).fetchone()
        duplicate = connection.execute(
            """
            SELECT loan_id FROM loans
            WHERE book_id = ? AND member_id = ? AND returned_date IS NULL
            """,
            (book_id, member_id),
        ).fetchone()
        if book is None or book["available_copies"] < 1:
            raise ValueError("This book is not currently available.")
        if member is None or member["status"] != "Active":
            raise ValueError("Only active members can borrow books.")
        if duplicate:
            raise ValueError("This member already has an active loan for this book.")

        cursor = connection.execute(
            """
            INSERT INTO loans
                (book_id, member_id, borrowed_date, due_date, status)
            VALUES (?, ?, ?, ?, 'Borrowed')
            """,
            (book_id, member_id, borrowed.isoformat(), due.isoformat()),
        )
        connection.execute(
            """
            UPDATE books SET available_copies = available_copies - 1
            WHERE book_id = ?
            """,
            (book_id,),
        )
        return inserted_id(cursor)


def calculate_fine(due_date: str, returned_date: Optional[str] = None) -> tuple[int, int]:
    due = date.fromisoformat(due_date)
    returned = date.fromisoformat(returned_date) if returned_date else date.today()
    overdue_days = max((returned - due).days, 0)
    return overdue_days, overdue_days * DAILY_FINE_NAIRA


def refresh_overdue_statuses() -> None:
    today = date.today().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE loans SET status = 'Overdue'
            WHERE returned_date IS NULL AND due_date < ?
            """,
            (today,),
        )
        connection.execute(
            """
            UPDATE loans SET status = 'Borrowed'
            WHERE returned_date IS NULL AND due_date >= ? AND status = 'Overdue'
            """,
            (today,),
        )


def list_active_loans() -> list[sqlite3.Row]:
    refresh_overdue_statuses()
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT l.loan_id, m.membership_number, m.full_name,
                   b.title, b.isbn, l.borrowed_date, l.due_date, l.status
            FROM loans l
            JOIN books b ON b.book_id = l.book_id
            JOIN members m ON m.member_id = l.member_id
            WHERE l.returned_date IS NULL
            ORDER BY l.due_date, m.full_name
            """
        ).fetchall()


def return_book(loan_id: int, returned_date: Optional[str] = None) -> dict:
    returned = date.fromisoformat(returned_date) if returned_date else date.today()
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        loan = connection.execute(
            """
            SELECT loan_id, book_id, borrowed_date, due_date, returned_date
            FROM loans WHERE loan_id = ?
            """,
            (loan_id,),
        ).fetchone()
        if loan is None:
            raise ValueError("Loan not found.")
        if loan["returned_date"] is not None:
            raise ValueError("This book has already been returned.")
        if returned < date.fromisoformat(loan["borrowed_date"]):
            raise ValueError("Return date cannot be earlier than the borrowing date.")
        if returned < date.fromisoformat(loan["due_date"]):
            overdue_days, fine_amount = 0, 0
        else:
            overdue_days, fine_amount = calculate_fine(
                loan["due_date"], returned.isoformat()
            )
        connection.execute(
            """
            UPDATE loans
            SET returned_date = ?, status = 'Returned', fine_amount = ?
            WHERE loan_id = ?
            """,
            (returned.isoformat(), fine_amount, loan_id),
        )
        connection.execute(
            """
            UPDATE books SET available_copies = available_copies + 1
            WHERE book_id = ?
            """,
            (loan["book_id"],),
        )
    return {"overdue_days": overdue_days, "fine_amount": fine_amount}


def list_loan_history(search_text: str = "", status: str = "All") -> list[sqlite3.Row]:
    refresh_overdue_statuses()
    search = f"%{search_text.strip()}%"
    status_filter = "%" if status == "All" else status
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT l.loan_id, m.membership_number, m.full_name,
                   b.title, l.borrowed_date, l.due_date,
                   l.returned_date, l.status, l.fine_amount
            FROM loans l
            JOIN books b ON b.book_id = l.book_id
            JOIN members m ON m.member_id = l.member_id
            WHERE (m.full_name LIKE ? OR m.membership_number LIKE ?
                   OR b.title LIKE ?)
              AND l.status LIKE ?
            ORDER BY l.loan_id DESC
            """,
            (search, search, search, status_filter),
        ).fetchall()


def list_overdue_loans() -> list[dict]:
    refresh_overdue_statuses()
    today = date.today()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT l.loan_id, m.membership_number, m.full_name, m.email, m.phone,
                   b.title, l.borrowed_date, l.due_date
            FROM loans l
            JOIN books b ON b.book_id = l.book_id
            JOIN members m ON m.member_id = l.member_id
            WHERE l.returned_date IS NULL AND l.due_date < ?
            ORDER BY l.due_date
            """,
            (today.isoformat(),),
        ).fetchall()
    return [
        dict(row)
        | {
            "overdue_days": (today - date.fromisoformat(row["due_date"])).days,
            "current_fine": (
                today - date.fromisoformat(row["due_date"])
            ).days
            * DAILY_FINE_NAIRA,
        }
        for row in rows
    ]


# ----------------------------- Payments -----------------------------


def list_outstanding_fines() -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT l.loan_id, m.member_id, m.membership_number, m.full_name,
                   m.email, b.title, l.returned_date, l.fine_amount,
                   COALESCE((
                       SELECT p.payment_status FROM payments p
                       WHERE p.loan_id = l.loan_id
                       ORDER BY p.payment_id DESC LIMIT 1
                   ), 'Not started') AS payment_status
            FROM loans l
            JOIN books b ON b.book_id = l.book_id
            JOIN members m ON m.member_id = l.member_id
            WHERE l.fine_amount > 0
              AND NOT EXISTS (
                  SELECT 1 FROM payments successful
                  WHERE successful.loan_id = l.loan_id
                    AND successful.payment_status = 'Successful'
              )
            ORDER BY l.loan_id DESC
            """
        ).fetchall()


def save_pending_payment(
    loan_id: int,
    member_id: int,
    amount: int,
    reference: str,
    authorization_url: str,
) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO payments
                (loan_id, member_id, amount, payment_reference,
                 payment_status, authorization_url)
            VALUES (?, ?, ?, ?, 'Pending', ?)
            """,
            (loan_id, member_id, amount, reference, authorization_url),
        )
        return inserted_id(cursor)


def update_payment_status(reference: str, status: str) -> None:
    if status not in ("Pending", "Successful", "Failed"):
        raise ValueError("Invalid payment status.")
    payment_date = datetime.now().isoformat(timespec="seconds") if status == "Successful" else None
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE payments
            SET payment_status = ?, payment_date = ?
            WHERE payment_reference = ?
            """,
            (status, payment_date, reference),
        )


def list_payments() -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT p.payment_id, p.payment_reference, m.full_name,
                   b.title, p.amount, p.payment_status, p.payment_date
            FROM payments p
            JOIN members m ON m.member_id = p.member_id
            JOIN loans l ON l.loan_id = p.loan_id
            JOIN books b ON b.book_id = l.book_id
            ORDER BY p.payment_id DESC
            """
        ).fetchall()


def get_payment(reference: str) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM payments WHERE payment_reference = ?", (reference,)
        ).fetchone()


# ----------------------------- Dashboard -----------------------------


def get_dashboard_statistics() -> dict:
    refresh_overdue_statuses()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM books) AS book_titles,
                (SELECT COALESCE(SUM(total_copies), 0) FROM books) AS total_books,
                (SELECT COALESCE(SUM(available_copies), 0) FROM books) AS available_books,
                (SELECT COUNT(*) FROM members WHERE status = 'Active') AS active_members,
                (SELECT COUNT(*) FROM loans WHERE returned_date IS NULL) AS active_loans,
                (SELECT COUNT(*) FROM loans WHERE status = 'Overdue') AS overdue_loans,
                (SELECT COALESCE(SUM(amount), 0) FROM payments
                    WHERE payment_status = 'Successful') AS fines_collected
            """
        ).fetchone()
    return dict(row)


def get_recent_loans(limit: int = 8) -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT l.loan_id, m.full_name, b.title, l.borrowed_date,
                   l.due_date, l.status
            FROM loans l
            JOIN books b ON b.book_id = l.book_id
            JOIN members m ON m.member_id = l.member_id
            ORDER BY l.loan_id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()


def seed_demo_data() -> None:
    """Insert sample books, members and loans without duplicating them."""
    categories = {row["category_name"]: row["category_id"] for row in get_categories()}
    with get_connection() as connection:
        if connection.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
            books = [
                ("9780132350884", "Clean Code", "Robert C. Martin", "Technology", 2008, 3),
                ("9780061120084", "To Kill a Mockingbird", "Harper Lee", "Fiction", 1960, 2),
                ("9780143127741", "Sapiens", "Yuval Noah Harari", "History", 2015, 2),
                ("9781617294136", "Grokking Algorithms", "Aditya Bhargava", "Technology", 2016, 2),
                ("9781400079179", "The Da Vinci Code", "Dan Brown", "Fiction", 2003, 1),
            ]
            for isbn, title, author, category, year, copies in books:
                connection.execute(
                    """
                    INSERT INTO books
                        (isbn, title, author, category_id, publication_year,
                         total_copies, available_copies)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (isbn, title, author, categories[category], year, copies, copies),
                )
        if connection.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0:
            members = [
                ("LIB-DEMO-001", "Amara Okafor", "amara@example.com", "08030000001", "Lagos"),
                ("LIB-DEMO-002", "Daniel Mensah", "daniel@example.com", "08030000002", "Abuja"),
                ("LIB-DEMO-003", "Zainab Bello", "zainab@example.com", "08030000003", "Kano"),
            ]
            for number, name, email, phone, address in members:
                connection.execute(
                    """
                    INSERT INTO members
                        (membership_number, full_name, email, phone, address,
                         registration_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'Active')
                    """,
                    (number, name, email, phone, address, date.today().isoformat()),
                )
