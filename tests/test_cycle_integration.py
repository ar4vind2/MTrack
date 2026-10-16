from app import app
from config import get_db_connection


def login_client(client, user_id=1, role_name="Employee", employee_id=1):
    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-csrf-token"
        sess["user_id"] = user_id
        sess["role_name"] = role_name
        if employee_id:
            sess["employee_id"] = employee_id
    return {"X-CSRF-Token": "test-csrf-token"}


def test_appraisal_form_get_cycle_id():
    client = app.test_client()
    login_client(client, user_id=1, role_name="Employee", employee_id=1)

    response = client.get("/appraisal-form")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    # Ensure cycle_id is present in select options
    assert 'name="cycle_id"' in html
    assert 'Annual Appraisal 2026-27' in html


def test_appraisal_form_post_saves_cycle_id():
    client = app.test_client()
    headers = login_client(client, user_id=1, role_name="Employee", employee_id=1)

    form_data = {
        "cycle_id": "1",
        "achievements": "Automated end-to-end cycle_id integration test suite.",
        "challenges": "Adapting legacy cycle string queries.",
        "certifications": "PostgreSQL Certified Professional",
        "training_completed": "Database Normalization & Indexing",
        "future_goals": "Principal Technical Architect",
        "suggestions": "Streamline review workflow",
        "csrf_token": "test-csrf-token"
    }

    response = client.post("/appraisal-form", data=form_data, headers=headers)
    assert response.status_code == 302
    assert "/self-appraisal" in response.headers["Location"]

    # Verify directly in PostgreSQL database that cycle_id was recorded
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cycle_id, employee_id, achievements FROM self_appraisal WHERE employee_id = 1 AND cycle_id = 1")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1  # cycle_id is 1
        assert row[1] == 1  # employee_id is 1
    finally:
        conn.close()


def test_self_appraisal_page_renders_cycle_data():
    client = app.test_client()
    login_client(client, user_id=1, role_name="Employee", employee_id=1)

    response = client.get("/self-appraisal")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Annual Appraisal 2026-27" in html
    assert "Automated end-to-end cycle_id integration test suite." in html


def test_manager_review_appraisal_views():
    client = app.test_client()
    login_client(client, user_id=2, role_name="Manager", employee_id=1)

    # 1. Review appraisal list page
    response = client.get("/review-appraisal")
    assert response.status_code == 200

    # 2. Review individual employee appraisal page
    detail_response = client.get("/review-employee-appraisal/5")
    assert detail_response.status_code == 200
    html = detail_response.get_data(as_text=True)
    assert 'name="cycle_id" value="1"' in html or 'name="cycle_id" value=\'1\'' in html or 'value="1"' in html


def test_manager_evaluation_submission():
    client = app.test_client()
    headers = login_client(client, user_id=2, role_name="Manager", employee_id=1)

    data = {
        "cycle_id": "1",
        "productivity": "4.5",
        "quality_of_work": "4.5",
        "teamwork": "5.0",
        "communication": "4.5",
        "problem_solving": "4.5",
        "initiative": "4.5",
        "compliance": "5.0",
        "self_goals_met": "4.5",
        "self_achievements": "4.5",
        "self_strengths": "4.5",
        "self_improvements": "4.0",
        "self_challenges": "4.0",
        "self_training_completed": "5.0",
        "self_certifications": "5.0",
        "manager_comments": "Outstanding performance on database schema normalization.",
        "csrf_token": "test-csrf-token"
    }

    response = client.post("/submit-manager-evaluation/5", data=data, headers=headers)
    assert response.status_code == 302

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cycle_id, employee_id, total_score, status FROM manager_appraisal WHERE employee_id = 5 AND cycle_id = 1")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1
        assert float(row[2]) > 0

        # Check performance_result upsert
        cur.execute("SELECT cycle_id, employee_id, manager_score, self_appraisal_score FROM performance_result WHERE employee_id = 5 AND cycle_id = 1")
        pr_row = cur.fetchone()
        assert pr_row is not None
        assert pr_row[0] == 1
        assert float(pr_row[2]) > 0
    finally:
        conn.close()


def test_behaviour_rating_submission():
    client = app.test_client()
    headers = login_client(client, user_id=2, role_name="Manager", employee_id=1)

    data = {
        "employee_id": "5",
        "cycle_id": "1",
        "integrity": "5",
        "professionalism": "5",
        "leadership": "4",
        "accountability": "5",
        "time_management": "4",
        "adaptability": "5",
        "learning_ability": "5",
        "remarks": "Consistently displays exemplary professional behavior.",
        "csrf_token": "test-csrf-token"
    }

    response = client.post("/save-behaviour-rating", data=data, headers=headers)
    assert response.status_code == 302

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cycle_id, employee_id, average_score FROM behaviour_rating WHERE employee_id = 5 AND cycle_id = 1")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1
        assert float(row[2]) > 0

        # Check performance_result behaviour score update
        cur.execute("SELECT cycle_id, employee_id, behaviour_score FROM performance_result WHERE employee_id = 5 AND cycle_id = 1")
        pr_row = cur.fetchone()
        assert pr_row is not None
        assert pr_row[0] == 1
        assert float(pr_row[2]) > 0
    finally:
        conn.close()


def test_api_performance_history_cycle_id():
    client = app.test_client()
    login_client(client, user_id=1, role_name="Employee", employee_id=1)

    response = client.get("/api/performance-history/1")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    if len(data) > 0:
        record = data[0]
        assert "cycle_id" in record
        assert "cycle_name" in record
        assert any(r["cycle_id"] == 1 for r in data) or record["cycle_id"] is not None


def test_manager_dashboard_and_evaluations_pages():
    client = app.test_client()
    login_client(client, user_id=2, role_name="Manager", employee_id=2)

    m_dash = client.get("/manager-dashboard")
    assert m_dash.status_code == 200

    team_eval = client.get("/api/manager/team-evaluations")
    assert team_eval.status_code == 200
    data = team_eval.get_json()
    assert data["success"] is True


def test_employee_dashboard_and_performance_data():
    client = app.test_client()
    login_client(client, user_id=1, role_name="Employee", employee_id=1)

    dash_html = client.get("/employee_dashboard.html")
    assert dash_html.status_code == 200

    dash_data = client.get("/employee")
    assert dash_data.status_code == 200
    payload = dash_data.get_json()
    assert payload["success"] is True
    assert payload["performance"]["cycle_id"] is not None
    assert "cycle_name" in payload["performance"]
