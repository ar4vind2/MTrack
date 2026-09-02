# MTrack

MTrack is a Flask and PostgreSQL employee performance-management application. It currently provides role-based login, employee and manager dashboards, notifications, and HR-managed KRA/KPI master data and assignments.

## Local setup

1. Create and activate a Python 3.13 virtual environment.
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create local configuration from the safe template:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Generate a random `SECRET_KEY`, update the database values in `.env`, then create a new PostgreSQL database.
5. Apply the baseline schema to a new database:

   ```powershell
   psql -h localhost -U mtrack_app -d mtrack -f migrations/001_initial_schema.sql
   ```

6. Optionally create the development users listed in `seed_users.py`:

   ```powershell
   python seed_users.py
   ```

7. Start the application:

   ```powershell
   python app.py
   ```

Open `http://127.0.0.1:5000`.

## Security configuration

- `SECRET_KEY` is mandatory. The application will not start without it.
- Set `APP_ENV=development` only for local work. Any other value disables Flask debug mode and sets secure session cookies.
- All unsafe HTTP requests require a session-bound CSRF token.
- KRA/KPI administration is restricted to HR and Admin roles.
- `.env` is intentionally ignored by Git. Never commit database passwords or production secrets.

## Tests

Run the fast security checks with:

```powershell
pytest -q
```

The suite does not require a running database. Database-backed flows should be covered by integration tests before deployment.

## Database changes

See [migrations/README.md](migrations/README.md) before applying schema changes to an existing database.
