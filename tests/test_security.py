from app import app


def test_health_check_is_public():
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_unsafe_api_request_requires_csrf_token():
    client = app.test_client()
    client.get("/login")

    response = client.post(
        "/api/auth/login",
        json={"username": "employee", "password": "password"}
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid or missing CSRF token."


def test_csrf_token_endpoint_creates_a_session_token():
    client = app.test_client()

    response = client.get("/api/csrf-token")

    assert response.status_code == 200
    assert response.get_json()["csrf_token"]


def test_kra_management_requires_hr_or_admin_access():
    client = app.test_client()

    unauthenticated_response = client.get("/kra-management")

    assert unauthenticated_response.status_code == 302
    assert unauthenticated_response.headers["Location"].endswith("/login")

    with client.session_transaction() as flask_session:
        flask_session["user_id"] = 1
        flask_session["role_name"] = "Employee"

    employee_response = client.get("/kra-management")

    assert employee_response.status_code == 403


def test_database_diagnostic_endpoint_is_not_exposed():
    client = app.test_client()

    response = client.get("/api/test-db")

    assert response.status_code == 404
