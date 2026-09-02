import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_required_env(name):
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"{name} must be set in the environment.")

    return value


def get_db_connection():
    return psycopg2.connect(
        host=get_required_env("DB_HOST"),
        port=get_required_env("DB_PORT"),
        database=get_required_env("DB_NAME"),
        user=get_required_env("DB_USER"),
        password=get_required_env("DB_PASSWORD")
    )
