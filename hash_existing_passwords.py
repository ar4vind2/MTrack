
from werkzeug.security import generate_password_hash
from config import get_db_connection


def hash_existing_passwords():
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, username, password FROM users"
            )
            users = cursor.fetchall()

            updated = 0
            skipped = 0

            for user_id, username, password in users:
                if not password:
                    skipped += 1
                    print(f"Skipped {username}: empty password")
                    continue

                # Do not hash existing Werkzeug hashes again
                if password.startswith(("scrypt:", "pbkdf2:")):
                    skipped += 1
                    continue

                hashed_password = generate_password_hash(password)

                cursor.execute(
                    """
                    UPDATE users
                    SET password = %s
                    WHERE user_id = %s
                    """,
                    (hashed_password, user_id)
                )

                updated += 1

        conn.commit()

        print(f"Successfully hashed: {updated}")
        print(f"Skipped: {skipped}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    hash_existing_passwords()