import pytest
from app import app


def login_client(client, user_id=1, role_name="Employee", employee_id=1):
    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-csrf-token"
        sess["user_id"] = user_id
        sess["role_name"] = role_name
        if employee_id:
            sess["employee_id"] = employee_id
    return {"X-CSRF-Token": "test-csrf-token"}


def test_team_evaluations_no_duplicates():
    client = app.test_client()
    login_client(client, user_id=2, role_name="Manager", employee_id=2)

    response = client.get("/api/manager/team-evaluations")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Ensure no duplicate employee IDs in team evaluations
    employee_ids = [eval_rec["employee_id"] for eval_rec in data["evaluations"]]
    assert len(employee_ids) == len(set(employee_ids)), f"Duplicate employee records found: {employee_ids}"


def test_review_attendance_page_rendering():
    client = app.test_client()
    login_client(client, user_id=2, role_name="Manager", employee_id=1)

    response = client.get("/review-attendance")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Check page title and structure
    assert "<h4>Team Attendance Review</h4>" in html
    assert "user-avatar-circle" in html
    assert "images.unsplash.com" not in html
    # Check that attendance record was rendered for the manager's team
    assert any(emp in html for emp in ["Akhil Thomas", "Meera Joseph", "Test Employee"])
    assert "No attendance records found." not in html


def test_no_external_avatar_images_across_pages():
    client = app.test_client()

    # Manager pages
    login_client(client, user_id=2, role_name="Manager", employee_id=2)
    manager_urls = [
        "/manager-dashboard",
        "/team-evaluation",
        "/review-attendance",
        "/review-appraisal",
        "/behaviour-rating",
        "/feedback-360",
        "/approve-leaves",
        "/profile"
    ]
    for url in manager_urls:
        resp = client.get(url)
        assert resp.status_code == 200, f"Failed on {url}"
        content = resp.get_data(as_text=True)
        assert "images.unsplash.com" not in content, f"Unsplash image found in {url}"
        assert "ui-avatars.com" not in content, f"ui-avatars found in {url}"
        assert "user-avatar-circle" in content, f"user-avatar-circle missing in {url}"

    # Employee pages
    login_client(client, user_id=1, role_name="Employee", employee_id=1)
    employee_urls = [
        "/employee-dashboard",
        "/my-appraisals",
        "/self-appraisal",
        "/employee-goals",
        "/employee-attendance",
        "/leave-request",
        "/requested-leaves",
        "/employee-training"
    ]
    for url in employee_urls:
        resp = client.get(url)
        assert resp.status_code == 200, f"Failed on {url}"
        content = resp.get_data(as_text=True)
        assert "images.unsplash.com" not in content, f"Unsplash image found in {url}"
        assert "ui-avatars.com" not in content, f"ui-avatars found in {url}"
        assert "user-avatar-circle" in content, f"user-avatar-circle missing in {url}"

    # HR pages
    login_client(client, user_id=3, role_name="Human Resources", employee_id=3)
    hr_urls = [
        "/hr-dashboard",
        "/performance-results",
        "/manage-training",
        "/kpi-management",
        "/kpi-records",
        "/assign-kpi",
        "/assign-kra",
        "/kra-kpi-report"
    ]
    for url in hr_urls:
        resp = client.get(url)
        assert resp.status_code == 200, f"Failed on {url}"
        content = resp.get_data(as_text=True)
        assert "images.unsplash.com" not in content, f"Unsplash image found in {url}"
        assert "ui-avatars.com" not in content, f"ui-avatars found in {url}"
        assert "user-avatar-circle" in content, f"user-avatar-circle missing in {url}"


def test_header_titles_standardized_and_no_bracketed_noise():
    client = app.test_client()

    # Manager
    login_client(client, user_id=2, role_name="Manager", employee_id=2)
    manager_checks = {
        "/manager-dashboard": "<h4>Manager Dashboard</h4>",
        "/team-evaluation": "<h4>Team Appraisal & Behaviour Evaluation</h4>",
        "/review-attendance": "<h4>Team Attendance Review</h4>",
        "/review-appraisal": "<h4>Review Employee Appraisals</h4>",
        "/behaviour-rating": "<h4>Behavioural Assessment & Rating</h4>",
        "/feedback-360": "<h4>360-Degree Feedback</h4>",
        "/approve-leaves": "<h4>Leave Approvals</h4>",
    }
    for url, expected_h4 in manager_checks.items():
        resp = client.get(url)
        content = resp.get_data(as_text=True)
        assert expected_h4 in content, f"Expected '{expected_h4}' in {url}"
        assert "(Member 4 Module)" not in content
        assert "(Manager)" not in content

    # Employee
    login_client(client, user_id=1, role_name="Employee", employee_id=1)
    employee_checks = {
        "/employee-dashboard": "<h4>Employee Dashboard</h4>",
        "/my-appraisals": "<h4>My Performance Appraisals</h4>",
        "/self-appraisal": "<h4>Self-Appraisal Summary</h4>",
        "/employee-goals": "<h4>Goals & Key Result Areas</h4>",
        "/employee-attendance": "<h4>Attendance & Leave Records</h4>",
        "/leave-request": "<h4>Leave Request Form</h4>",
        "/requested-leaves": "<h4>My Leave Requests</h4>",
        "/employee-training": "<h4>Training & Skill Certifications</h4>",
    }
    for url, expected_h4 in employee_checks.items():
        resp = client.get(url)
        content = resp.get_data(as_text=True)
        assert expected_h4 in content, f"Expected '{expected_h4}' in {url}"
        assert "(Employee Progress)" not in content
        assert "(Employee View)" not in content

    # HR
    login_client(client, user_id=3, role_name="Human Resources", employee_id=3)
    hr_checks = {
        "/hr-dashboard": "<h4>HR Administration Dashboard</h4>",
        "/performance-results": "<h4>Performance Evaluation Results</h4>",
        "/manage-training": "<h4>Training Program Management</h4>",
        "/kpi-management": "<h4>KPI Management</h4>",
        "/kpi-records": "<h4>KPI Records</h4>",
        "/assign-kpi": "<h4>Assign Key Performance Indicator</h4>",
        "/assign-kra": "<h4>Assign Key Result Area</h4>",
        "/kra-kpi-report": "<h4>KRA & KPI Performance Report</h4>",
    }
    for url, expected_h4 in hr_checks.items():
        resp = client.get(url)
        content = resp.get_data(as_text=True)
        assert expected_h4 in content, f"Expected '{expected_h4}' in {url}"
        assert "(HR Admin)" not in content


def test_hr_dashboard_data_api():
    client = app.test_client()

    # 1. Unauthenticated request rejected
    unauth = client.get("/api/hr/dashboard-data")
    assert unauth.status_code == 401

    # 2. Employee role rejected
    login_client(client, user_id=1, role_name="Employee", employee_id=1)
    emp_resp = client.get("/api/hr/dashboard-data")
    assert emp_resp.status_code == 403

    # 3. HR role succeeds
    login_client(client, user_id=3, role_name="Human Resources", employee_id=3)
    resp = client.get("/api/hr/dashboard-data")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "stats" in data
    assert "total_employees" in data["stats"]
    assert "completion" in data
    assert "completed" in data["completion"]
    assert "department_performance" in data
    assert "categories" in data["department_performance"]
    assert "monthly_trend" in data
    assert "series" in data["monthly_trend"]
    assert "recommendations" in data


def test_hr_promotion_and_increment_approval():
    from config import get_db_connection
    client = app.test_client()
    headers = login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    conn = get_db_connection()
    orig_desig = 1
    try:
        cur = conn.cursor()
        cur.execute("SELECT designation_id FROM employees WHERE employee_id = 1")
        row = cur.fetchone()
        if row:
            orig_desig = row[0]
    finally:
        conn.close()

    try:
        # 1. Test Promotion Approval
        promo_data = {
            "employee_id": 1,
            "reason": "Exemplary technical leadership in database architecture."
        }
        promo_resp = client.post("/api/hr/approve-promotion", json=promo_data, headers=headers)
        assert promo_resp.status_code == 200
        promo_res = promo_resp.get_json()
        assert promo_res["success"] is True

        # 2. Test Increment Approval
        incr_data = {
            "employee_id": 1,
            "increment_amount": 7500,
            "reason": "Annual merit increase."
        }
        incr_resp = client.post("/api/hr/approve-increment", json=incr_data, headers=headers)
        assert incr_resp.status_code == 200
        incr_res = incr_resp.get_json()
        assert incr_res["success"] is True
    finally:
        restore_conn = get_db_connection()
        try:
            rcur = restore_conn.cursor()
            rcur.execute("UPDATE employees SET designation_id = %s WHERE employee_id = 1", (orig_desig,))
            restore_conn.commit()
        finally:
            restore_conn.close()



def test_self_appraisal_overall_rating_persists():
    from config import get_db_connection
    client = app.test_client()
    headers = login_client(client, user_id=1, role_name="Employee", employee_id=1)

    form_data = {
        "cycle_id": "1",
        "achievements": "Spearheaded core performance calculations & normalization.",
        "challenges": "Legacy data consistency.",
        "certifications": "PostgreSQL Professional",
        "training_completed": "Database Architecture",
        "future_goals": "Engineering Director",
        "suggestions": "Automate cycle evaluations",
        "overall_self_rating": "5",
        "csrf_token": "test-csrf-token"
    }

    resp = client.post("/appraisal-form", data=form_data, headers=headers)
    assert resp.status_code == 302

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT self_score FROM self_appraisal WHERE employee_id = 1 AND cycle_id = 1 ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        assert row is not None
        # 5 * 20 = 100.0
        assert float(row[0]) == 100.0
    finally:
        conn.close()


def test_leave_approval_populates_approved_by():
    from config import get_db_connection
    client = app.test_client()
    headers = login_client(client, user_id=2, role_name="Manager", employee_id=2)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO leave_requests (employee_id, leave_type, from_date, to_date, number_of_days, reason, status, applied_on)
            VALUES (1, 'Casual Leave', CURRENT_DATE + INTERVAL '10 days', CURRENT_DATE + INTERVAL '11 days', 2, 'Personal emergency', 'Pending', NOW())
            RETURNING leave_id
        """)
        leave_id = cur.fetchone()[0]
        conn.commit()

        # Manager approves the leave request
        resp = client.post("/approve-leaves", json={"leave_id": leave_id, "status": "Approved"}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

        # Verify approved_by is set to manager's employee_id (2)
        cur.execute("SELECT status, approved_by FROM leave_requests WHERE leave_id = %s", (leave_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Approved"
        assert row[1] == 2
    finally:
        try:
            if 'cur' in locals() and 'leave_id' in locals():
                cur.execute("DELETE FROM leave_requests WHERE leave_id = %s", (leave_id,))
                conn.commit()
        except Exception:
            pass
        conn.close()


def test_employee_pages_role_and_badge_consistency():
    client = app.test_client()
    login_client(client, user_id=1, role_name="Employee", employee_id=1)

    employee_urls = [
        "/appraisal-form",
        "/self-appraisal",
        "/leave-request",
        "/requested-leaves",
        "/employee-training"
    ]
    for url in employee_urls:
        resp = client.get(url)
        assert resp.status_code == 200, f"Failed on {url}"
        html = resp.get_data(as_text=True)
        assert 'name="user-role" content="employee"' in html, f"Missing employee meta role in {url}"
        assert 'Employee' in html


def test_hr_dashboard_clean_titles():
    client = app.test_client()
    login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    resp = client.get("/hr-dashboard")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "(ApexCharts Line)" not in html
    assert "(Donut)" not in html
    assert "(ApexCharts Bar)" not in html


def test_performance_details_no_formula_box():
    client = app.test_client()
    login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    resp = client.get("/employee-performance-details?employee_id=1")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="performanceFormula"' not in html
    assert "Weighted Formula Calculation" not in html


def test_review_employee_appraisal_layout():
    client = app.test_client()
    login_client(client, user_id=2, role_name="Manager", employee_id=1)

    resp = client.get("/review-employee-appraisal/5")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '<aside class="sidebar">' in html
    assert '<nav class="topbar">' in html
    assert 'css/style.css' in html
    assert 'name="user-role" content="manager"' in html
    assert 'id="productivity"' in html
    assert 'id="totalScoreDisplay"' in html


def test_reportlab_and_openpyxl_generation():
    from config import get_db_connection
    client = app.test_client()
    login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    # 1. Test PDF generation
    pdf_resp = client.get("/api/reports/generate-pdf?title=Automated_Test_Report")
    assert pdf_resp.status_code == 200
    assert pdf_resp.data.startswith(b"%PDF")

    # 2. Test Excel generation
    xlsx_resp = client.get("/api/reports/generate-excel?title=Automated_Test_Export")
    assert xlsx_resp.status_code == 200

    # 3. Verify logging in report_history table
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT report_id, report_name, report_type FROM report_history WHERE report_name = 'Automated_Test_Report'")
        row = cur.fetchone()
        assert row is not None
        assert row[2] == "PDF"

        cur.execute("SELECT report_id, report_name, report_type FROM report_history WHERE report_name = 'Automated_Test_Export'")
        row_xl = cur.fetchone()
        assert row_xl is not None
        assert row_xl[2] == "Excel"
    finally:
        conn.close()


def test_admin_crud_endpoints():
    from config import get_db_connection
    client = app.test_client()
    headers = login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    # Users list
    u_resp = client.get("/api/admin/users", headers=headers)
    assert u_resp.status_code == 200
    assert len(u_resp.get_json()["users"]) >= 1

    # Employees list
    e_resp = client.get("/api/admin/employees", headers=headers)
    assert e_resp.status_code == 200
    assert len(e_resp.get_json()["employees"]) >= 1

    # Departments list
    d_resp = client.get("/api/admin/departments", headers=headers)
    assert d_resp.status_code == 200
    assert len(d_resp.get_json()["departments"]) >= 1

    # Designations list and creation
    desig_resp = client.get("/api/admin/designations", headers=headers)
    assert desig_resp.status_code == 200
    assert len(desig_resp.get_json()["designations"]) >= 1

