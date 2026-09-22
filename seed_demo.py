"""Add demonstration records without changing existing library data."""

import database


if __name__ == "__main__":
    database.initialise_database()
    database.seed_demo_data()
    print("Demo books and members are ready.")

