"""Tests for login, pages and the main Flask JSON routes."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import app as web_app
import database


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(database, "DATABASE_PATH", Path(self.temp_directory.name) / "routes.db")
        self.path_patch.start()
        database.initialise_database()
        web_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = web_app.app.test_client()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_directory.cleanup()

    def login(self):
        return self.client.post("/login", data={"username": "admin", "password": "admin123"})

    def test_dashboard_requires_login(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    def test_login_opens_dashboard(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Library Dashboard", response.data)

    def test_api_requires_login(self):
        response = self.client.get("/api/books")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_create_book_member_and_loan_through_api(self):
        self.login()
        category_id = self.client.get("/api/categories").get_json()["data"][0]["category_id"]
        book = self.client.post("/api/books", json={"isbn": "9780000000025", "title": "Web Test", "author": "Coder", "category_id": category_id, "publication_year": 2024, "total_copies": 1})
        member = self.client.post("/api/members", json={"full_name": "Ada Tester", "email": "ada@example.com", "phone": "08012345678", "address": "Lagos"})
        self.assertEqual(book.status_code, 201)
        self.assertEqual(member.status_code, 201)
        loan = self.client.post("/api/loans", json={"book_id": book.get_json()["data"]["book_id"], "member_id": member.get_json()["data"]["member_id"]})
        self.assertEqual(loan.status_code, 201)
        active = self.client.get("/api/loans/active").get_json()["data"]
        self.assertEqual(len(active), 1)

    def test_every_page_renders_with_shared_modal_and_its_script(self):
        self.login()
        pages = {
            "/books": b"js/books.js",
            "/members": b"js/members.js",
            "/lending": b"js/lending.js",
            "/history": b"js/history.js",
            "/overdue": b"js/overdue.js",
            "/payments": b"js/payments.js",
        }
        for path, script_name in pages.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'id="appModal"', response.data)
                self.assertIn(b'id="toastContainer"', response.data)
                self.assertIn(script_name, response.data)

    def test_category_book_update_and_delete_routes(self):
        self.login()
        category = self.client.post(
            "/api/categories", json={"category_name": "Poetry"}
        )
        self.assertEqual(category.status_code, 200)
        category_id = category.get_json()["data"]["category_id"]

        book = self.client.post(
            "/api/books",
            json={
                "isbn": "9780000000032",
                "title": "First Title",
                "author": "Test Author",
                "category_id": category_id,
                "publication_year": 2022,
                "total_copies": 2,
            },
        )
        book_id = book.get_json()["data"]["book_id"]
        updated = self.client.put(
            f"/api/books/{book_id}",
            json={
                "isbn": "9780000000032",
                "title": "Updated Title",
                "author": "Test Author",
                "category_id": category_id,
                "publication_year": 2023,
                "total_copies": 3,
            },
        )
        self.assertTrue(updated.get_json()["success"])
        self.assertEqual(
            self.client.delete(f"/api/books/{book_id}").status_code, 200
        )

    def test_missing_number_returns_clear_validation_error(self):
        self.login()
        response = self.client.post(
            "/api/books",
            json={"isbn": "1", "title": "No Category", "author": "Tester"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Category Id is required", response.get_json()["message"])

    def test_member_update_return_history_and_overdue_routes(self):
        self.login()
        category_id = self.client.get("/api/categories").get_json()["data"][0]["category_id"]
        book = self.client.post(
            "/api/books",
            json={"isbn": "9780000000049", "title": "Late Book", "author": "Coder", "category_id": category_id, "publication_year": 2020, "total_copies": 1},
        ).get_json()["data"]
        member = self.client.post(
            "/api/members",
            json={"full_name": "Before Name", "email": "before@example.com", "phone": "08011111111", "address": "Lagos"},
        ).get_json()["data"]
        update = self.client.put(
            f"/api/members/{member['member_id']}",
            json={"full_name": "After Name", "email": "after@example.com", "phone": "08022222222", "address": "Abuja", "status": "Active"},
        )
        self.assertTrue(update.get_json()["success"])

        borrowed = date.today() - timedelta(days=20)
        due = date.today() - timedelta(days=6)
        loan = self.client.post(
            "/api/loans",
            json={"book_id": book["book_id"], "member_id": member["member_id"], "borrowed_date": borrowed.isoformat(), "due_date": due.isoformat()},
        ).get_json()["data"]
        self.assertEqual(len(self.client.get("/api/overdue").get_json()["data"]), 1)
        returned = self.client.post(
            f"/api/loans/{loan['loan_id']}/return",
            json={"returned_date": date.today().isoformat()},
        )
        self.assertGreater(returned.get_json()["data"]["fine_amount"], 0)
        history = self.client.get("/api/history?status=Returned").get_json()["data"]
        self.assertEqual(len(history), 1)

    @patch.object(web_app.paystack_service, "initialise_transaction")
    @patch.object(web_app.paystack_service, "create_reference", return_value="DL-TEST-REF")
    def test_payment_initialise_and_verify_routes(self, _reference_mock, initialise_mock):
        self.login()
        category_id = database.get_categories()[0]["category_id"]
        book_id = database.add_book("9780000000056", "Fine Book", "Coder", category_id, 2020, 1)
        member_id = database.add_member("Fine Member", "fine@example.com", "08033333333", "Lagos")
        loan_id = database.borrow_book(
            book_id,
            member_id,
            (date.today() - timedelta(days=20)).isoformat(),
            (date.today() - timedelta(days=4)).isoformat(),
        )
        database.return_book(loan_id, date.today().isoformat())
        initialise_mock.return_value = {
            "reference": "DL-TEST-REF",
            "authorization_url": "https://checkout.paystack.com/test",
        }
        created = self.client.post(
            "/api/payments/initialise", json={"loan_id": loan_id}
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(
            created.get_json()["data"]["authorization_url"],
            "https://checkout.paystack.com/test",
        )
        with patch.object(
            web_app.paystack_service,
            "verify_transaction",
            return_value={"successful": True, "gateway_status": "success"},
        ):
            verified = self.client.post("/api/payments/DL-TEST-REF/verify")
        self.assertTrue(verified.get_json()["success"])
        payment_rows = self.client.get("/api/payments").get_json()["data"]["history"]
        self.assertEqual(payment_rows[0]["payment_status"], "Successful")


if __name__ == "__main__":
    unittest.main()
