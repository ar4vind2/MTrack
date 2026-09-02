from werkzeug.security import generate_password_hash
from config import get_db_connection


users = [
    {
        "username": "emp001",
        "password": "emp123",
        "role_id": 1
    },
    {
        "username": "manager001",
        "password": "manager123",
        "role_id": 2
    },
    {
        "username": "hr001",
        "password": "hr123",
        "role_id": 3
    },
    {
        "username": "admin",
        "password": "admin123",
        "role_id": 4
    }
]


connection = get_db_connection()

try:

    cursor = connection.cursor()

    for user in users:

        password_hash = generate_password_hash(
            user["password"]
        )

        cursor.execute("""
            INSERT INTO users
                (username, password, role_id)
            VALUES
                (%s, %s, %s)
        """, (
            user["username"],
            password_hash,
            user["role_id"]
        ))

    connection.commit()

    print("Users created successfully.")

except Exception as e:

    connection.rollback()

    print("Error:", e)

finally:

    cursor.close()
    connection.close()