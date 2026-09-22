# Digital Library Book Lending and Management System by touchecodes

An educational full-stack project built with standard HTML5, CSS3 and JavaScript, a small Flask backend, SQLite and Paystack test payments. It covers book management, categories, member registration, searching, borrowing, returns, due dates, overdue tracking, borrowing history, an administrator dashboard and fine payments.

## Project structure

```text
DigitalLibraryWebSystem/
├── app.py                 Flask routes and JSON API
├── database.py            SQLite tables, SQL and business rules
├── paystack_service.py    Paystack test API requests
├── config.py              Project settings
├── seed_demo.py           Optional sample records
├── templates/             HTML5 pages
├── static/css/style.css   CSS3 design and responsive layout
├── static/js/             Vanilla JavaScript for each page
└── tests/                  Automated tests
```

## Install and run

Open a terminal in this project folder and run `python -m venv .venv`. Activate it with `.venv\Scripts\activate` on Windows or `source .venv/bin/activate` on macOS/Linux. Then run:

```bash
pip install -r requirements.txt
python seed_demo.py
python app.py
```

Open `http://127.0.0.1:5000` in a browser. Sign in with username `admin` and password `admin123`.

## Paystack test setup

Copy `.env.example` to `.env` and insert both Paystack test keys. The public key begins with `pk_test_`; the secret key begins with `sk_test_`. The backend needs the test secret key to create and verify a transaction. Never upload or present the real `.env` file.

## Run tests

```bash
python -m unittest discover -s tests -v
```

This project deliberately avoids high-level frontend frameworks and ORMs. The HTML, CSS, JavaScript, Flask routes and SQL are visible and can be explained directly.
