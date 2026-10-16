from routes.dashboard import (
    calculate_attendance_percentage,
    calculate_attendance_score,
)


def test_half_day_counts_as_half_of_a_present_day():
    assert calculate_attendance_percentage(8, 10, 1) == 85
    assert calculate_attendance_score(8, 10, 1) == 4


def test_attendance_calculation_without_half_days_is_unchanged():
    assert calculate_attendance_percentage(9, 10) == 90
    assert calculate_attendance_score(9, 10) == 5


def test_attendance_calculation_handles_no_working_days():
    assert calculate_attendance_percentage(0, 0, 1) == 0
    assert calculate_attendance_score(0, 0, 1) == 0


def test_employee_attendance_page_loads_without_holidays_table():
    from app import app
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-csrf-token"
        sess["user_id"] = 1
        sess["role_name"] = "Employee"
        sess["employee_id"] = 1

    response = client.get("/employee-attendance")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Attendance Summary" in html or "attendance" in html.lower()


def test_employee_leave_request_page_renders_leave_balances():
    from app import app
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-csrf-token"
        sess["user_id"] = 1
        sess["role_name"] = "Employee"
        sess["employee_id"] = 1

    response = client.get("/leave-request")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Casual Leave" in html or "Leave" in html


def test_performance_api_cycle_attendance():
    from app import app
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-csrf-token"
        sess["user_id"] = 1
        sess["role_name"] = "HR"

    response = client.get("/api/performance/1?cycle_id=1")
    assert response.status_code == 200
    data = response.get_json()
    assert "scores" in data
    assert "attendance" in data["scores"]
    assert 0 <= data["scores"]["attendance"] <= 100


def test_performance_results_cycle_attendance():
    from app import app
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-csrf-token"
        sess["user_id"] = 1
        sess["role_name"] = "HR"

    response = client.get("/api/performance-results?cycle_id=1")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    if data:
        assert "attendance_score" in data[0]
        assert 0 <= data[0]["attendance_score"] <= 100
