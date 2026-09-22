"""Automated tests for the core database rules."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test_library.db"
        self.path_patch = patch.object(database, "DATABASE_PATH", self.database_path)
        self.path_patch.start()
        database.initialise_database()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_directory.cleanup()

    def add_book_and_member(self):
        category_id = database.get_categories()[0]["category_id"]
        book_id = database.add_book("9780000000001", "Test Book", "Test Author", category_id, 2020, 2)
        member_id = database.add_member("Test Member", "member@example.com", "08000000000", "Test Address")
        return book_id, member_id

    def test_default_administrator_can_log_in(self):
        user = database.authenticate_user("admin", "admin123")
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "Librarian")

    def test_wrong_password_is_rejected(self):
        self.assertIsNone(database.authenticate_user("admin", "wrong"))

    def test_book_is_created_with_all_copies_available(self):
        book_id, _ = self.add_book_and_member()
        book = next(row for row in database.list_books() if row["book_id"] == book_id)
        self.assertEqual(book["total_copies"], 2)
        self.assertEqual(book["available_copies"], 2)

    def test_borrowing_reduces_available_copies(self):
        book_id, member_id = self.add_book_and_member()
        database.borrow_book(book_id, member_id)
        book = next(row for row in database.list_books() if row["book_id"] == book_id)
        self.assertEqual(book["available_copies"], 1)

    def test_returning_restores_copy_and_calculates_fine(self):
        book_id, member_id = self.add_book_and_member()
        loan_id = database.borrow_book(book_id, member_id, (date.today() - timedelta(days=20)).isoformat(), (date.today() - timedelta(days=6)).isoformat())
        result = database.return_book(loan_id, date.today().isoformat())
        self.assertEqual(result["overdue_days"], 6)
        self.assertEqual(result["fine_amount"], 6 * database.DAILY_FINE_NAIRA)
        book = next(row for row in database.list_books() if row["book_id"] == book_id)
        self.assertEqual(book["available_copies"], 2)

    def test_same_member_cannot_borrow_same_book_twice(self):
        book_id, member_id = self.add_book_and_member()
        database.borrow_book(book_id, member_id)
        with self.assertRaises(ValueError):
            database.borrow_book(book_id, member_id)

    def test_inactive_member_cannot_borrow(self):
        book_id, member_id = self.add_book_and_member()
        database.update_member(member_id, "Test Member", "member@example.com", "08000000000", "Test Address", "Inactive")
        with self.assertRaises(ValueError):
            database.borrow_book(book_id, member_id)

    def test_overdue_loan_is_detected(self):
        book_id, member_id = self.add_book_and_member()
        database.borrow_book(book_id, member_id, (date.today() - timedelta(days=20)).isoformat(), (date.today() - timedelta(days=6)).isoformat())
        overdue = database.list_overdue_loans()
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0]["overdue_days"], 6)


if __name__ == "__main__":
    unittest.main()
