import pytest
from app import app
from routes.reports import _get_appraisal_report_data


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_manager_self_services_accessible(client):
    """Verify that manager role can access self-service pages without 403."""
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["username"] = "manager_it"
        sess["role_name"] = "Manager"
        sess["employee_id"] = 1

    self_service_urls = [
        "/employee-attendance",
        "/leave-request",
        "/my-appraisals",
        "/employee-training",
        "/self-appraisal",
        "/employee-goals",
        "/requested-leaves",
    ]

    for url in self_service_urls:
        response = client.get(url)
        assert response.status_code == 200, f"Expected 200 for manager accessing {url}, got {response.status_code}"


def test_manager_report_scope_restricted_to_direct_reports():
    """Verify manager reports contain only manager and reportees, not the entire company."""
    # Manager IT is Rahul Menon (user_id=2, employee_id=1)
    rows, cycle_name = _get_appraisal_report_data(user_id=2, role_name="Manager", employee_id=1)

    assert len(rows) > 0
    # Must only contain EMP001 (manager) and his reportees (EMP004, EMP005, EMP006, EMP012)
    emp_codes = [r[0] for r in rows]
    assert "EMP001" in emp_codes
    assert "EMP005" in emp_codes  # Direct reportee
    assert "EMP008" not in emp_codes  # Belongs to Finance Manager Arun Kumar
    assert "EMP007" not in emp_codes  # Belongs to HR Manager Anjali Nair


def test_employee_dashboard_trend_breakdown(client):
    """Verify that employee dashboard returns categorized trends (monthly, quarterly, annual, all)."""
    with client.session_transaction() as sess:
        sess["user_id"] = 6
        sess["username"] = "employee01"
        sess["role_name"] = "Employee"
        sess["employee_id"] = 5

    res = client.get("/employee")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    trends = data.get("performance_trends", {})
    assert "monthly" in trends
    assert "quarterly" in trends
    assert "annual" in trends
    assert "all" in trends

    # Monthly should only have monthly appraisal cycles
    for item in trends["monthly"]:
        assert "quarter" not in item["name"].lower()
        assert "annual" not in item["name"].lower()

    # Quarterly should only have quarterly appraisal cycles
    for item in trends["quarterly"]:
        assert "quarter" in item["name"].lower() or any(q in item["name"].lower() for q in ["q1", "q2", "q3", "q4"])

    # Annual should only have annual appraisal cycles
    for item in trends["annual"]:
        assert "annual" in item["name"].lower() or "yearly" in item["name"].lower()


def test_dashboard_and_reports_score_synchronization(client):
    """Verify that employee dashboard and report generator produce identical scores for active cycle."""
    with client.session_transaction() as sess:
        sess["user_id"] = 6
        sess["username"] = "employee01"
        sess["role_name"] = "Employee"
        sess["employee_id"] = 5

    # 1. Fetch dashboard score
    dash_res = client.get("/employee")
    assert dash_res.status_code == 200
    dash_data = dash_res.get_json()
    dash_score = dash_data["performance"]["final_score"]
    cycle_id = dash_data["cycle_id"]

    # 2. Fetch report data for the same user
    rows, cycle_name = _get_appraisal_report_data(user_id=6, role_name="Employee", employee_id=5, cycle_id=cycle_id)
    assert len(rows) == 1
    report_score = rows[0][4]

    # Scores must be identical
    assert round(float(dash_score), 2) == round(float(report_score), 2)


def test_calibrated_rating_and_recommendation_thresholds():
    """Verify that the system ratings and recommendations match the exact specified criteria."""
    from routes.reports import _get_appraisal_report_data

    # Test through _get_appraisal_report_data
    rows, _ = _get_appraisal_report_data(user_id=6, role_name="Employee", employee_id=5)
    score, rating, rec = rows[0][4], rows[0][5], rows[0][6]

    if score >= 90.0:
        assert rating == "Outstanding"
        assert rec == "Promotion Recommended and Salary Increment Recommended"
    elif score >= 80.0:
        assert rating == "Excellent"
        if score >= 85.0:
            assert rec == "Salary Increment Recommended"
        else:
            assert rec == "No Immediate Action"
    elif score >= 70.0:
        assert rating == "Good"
        if score >= 75.0:
            assert rec == "No Immediate Action"
        else:
            assert rec == "Training / Development Recommended"
    elif score >= 60.0:
        assert rating == "Needs Improvement"
        assert rec == "Training / Development Recommended"
    else:
        assert rating == "Unsatisfactory"
        assert rec == "Training / Development Recommended"
