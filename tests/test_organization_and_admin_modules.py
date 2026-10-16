import pytest
from app import app
from config import get_db_connection


def login_client(client, user_id=3, role_name="Human Resources", employee_id=3):
    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-csrf-token"
        sess["user_id"] = user_id
        sess["role_name"] = role_name
        if employee_id:
            sess["employee_id"] = employee_id
    return {"X-CSRF-Token": "test-csrf-token"}


def test_admin_departments_views_and_crud():
    client = app.test_client()
    headers = login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    # 1. GET page
    resp = client.get("/admin/departments", headers=headers)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Department Management" in html
    assert "Add Department" in html

    # 2. POST create
    dept_name = "QA Automation & Quality"
    create_resp = client.post("/admin/departments", data={
        "department_name": dept_name,
        "casual_leave_limit": 14,
        "sick_leave_limit": 10,
        "privileged_leave_limit": 16,
        "csrf_token": "test-csrf-token"
    }, headers=headers, follow_redirects=True)
    assert create_resp.status_code == 200

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT department_id FROM departments WHERE department_name = %s", (dept_name,))
        row = cur.fetchone()
        assert row is not None
        dept_id = row[0]

        # 3. POST edit
        edit_resp = client.post(f"/admin/departments/edit/{dept_id}", data={
            "department_name": "QA & Quality Control",
            "casual_leave_limit": 15,
            "sick_leave_limit": 10,
            "privileged_leave_limit": 18,
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert edit_resp.status_code == 200

        cur.execute("SELECT department_name FROM departments WHERE department_id = %s", (dept_id,))
        assert cur.fetchone()[0] == "QA & Quality Control"

        # 4. POST delete
        del_resp = client.post(f"/admin/departments/delete/{dept_id}", data={
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert del_resp.status_code == 200

        cur.execute("SELECT department_id FROM departments WHERE department_id = %s", (dept_id,))
        assert cur.fetchone() is None
    finally:
        conn.close()


def test_admin_branches_views_and_crud():
    client = app.test_client()
    headers = login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    # 1. GET page
    resp = client.get("/admin/branches", headers=headers)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Branch Management" in html
    assert "Add Branch" in html

    # 2. POST create
    branch_name = "Cochin Tech Hub"
    create_resp = client.post("/admin/branches", data={
        "branch_name": branch_name,
        "location": "Kakkanad, Kochi",
        "csrf_token": "test-csrf-token"
    }, headers=headers, follow_redirects=True)
    assert create_resp.status_code == 200

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT branch_id FROM branches WHERE branch_name = %s", (branch_name,))
        row = cur.fetchone()
        assert row is not None
        branch_id = row[0]

        # 3. POST edit
        edit_resp = client.post(f"/admin/branches/edit/{branch_id}", data={
            "branch_name": "Kochi Infopark Branch",
            "location": "Infopark Phase 2, Kochi",
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert edit_resp.status_code == 200

        cur.execute("SELECT branch_name, location FROM branches WHERE branch_id = %s", (branch_id,))
        updated_row = cur.fetchone()
        assert updated_row[0] == "Kochi Infopark Branch"
        assert updated_row[1] == "Infopark Phase 2, Kochi"

        # 4. POST delete
        del_resp = client.post(f"/admin/branches/delete/{branch_id}", data={
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert del_resp.status_code == 200

        cur.execute("SELECT branch_id FROM branches WHERE branch_id = %s", (branch_id,))
        assert cur.fetchone() is None
    finally:
        conn.close()


def test_admin_designations_views_and_crud():
    client = app.test_client()
    headers = login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    # 1. GET page
    resp = client.get("/admin/designations", headers=headers)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Designation Management" in html
    assert "Add Designation" in html

    # 2. POST create
    desig_name = "Staff AI Engineer"
    create_resp = client.post("/admin/designations", data={
        "designation_name": desig_name,
        "csrf_token": "test-csrf-token"
    }, headers=headers, follow_redirects=True)
    assert create_resp.status_code == 200

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT designation_id FROM designations WHERE designation_name = %s", (desig_name,))
        row = cur.fetchone()
        assert row is not None
        desig_id = row[0]

        # 3. POST edit
        edit_resp = client.post(f"/admin/designations/edit/{desig_id}", data={
            "designation_name": "Principal AI Architect",
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert edit_resp.status_code == 200

        cur.execute("SELECT designation_name FROM designations WHERE designation_id = %s", (desig_id,))
        assert cur.fetchone()[0] == "Principal AI Architect"

        # 4. POST delete
        del_resp = client.post(f"/admin/designations/delete/{desig_id}", data={
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert del_resp.status_code == 200

        cur.execute("SELECT designation_id FROM designations WHERE designation_id = %s", (desig_id,))
        assert cur.fetchone() is None
    finally:
        conn.close()


def test_admin_users_views_and_crud():
    client = app.test_client()
    headers = login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    # 1. GET page
    resp = client.get("/admin/users", headers=headers)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "User Accounts" in html
    assert "Add User Account" in html

    # 2. POST create
    username = "test_user_admin_flow"
    create_resp = client.post("/admin/users", data={
        "username": username,
        "password": "TemporaryPassword123!",
        "role_id": 3,
        "csrf_token": "test-csrf-token"
    }, headers=headers, follow_redirects=True)
    assert create_resp.status_code == 200

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        assert row is not None
        uid = row[0]

        # 3. POST edit
        edit_resp = client.post(f"/admin/users/edit/{uid}", data={
            "username": "test_user_admin_flow_mod",
            "role_id": 2,
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert edit_resp.status_code == 200

        cur.execute("SELECT username, role_id FROM users WHERE user_id = %s", (uid,))
        urow = cur.fetchone()
        assert urow[0] == "test_user_admin_flow_mod"
        assert urow[1] == 2

        # 4. POST delete
        del_resp = client.post(f"/admin/users/delete/{uid}", data={
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert del_resp.status_code == 200

        cur.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        assert cur.fetchone() is None
    finally:
        conn.close()


def test_admin_employees_views_and_onboarding():
    client = app.test_client()
    headers = login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    # 1. Directory GET
    resp = client.get("/admin/employees", headers=headers)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Employee Management" in html
    assert "Staff Directory" in html

    # 2. Add Employee GET
    add_resp = client.get("/admin/employees/add", headers=headers)
    assert add_resp.status_code == 200
    add_html = add_resp.get_data(as_text=True)
    assert "Add New Employee" in add_html
    assert "Employee Information Form" in add_html

    # 3. Add Employee POST
    emp_code = "EMP9999"
    create_resp = client.post("/admin/employees/add", data={
        "employee_code": emp_code,
        "first_name": "Rohan",
        "last_name": "Sharma",
        "email": "rohan.sharma@muthoot.com",
        "phone": "+91 9988776655",
        "employment_status": "Active",
        "csrf_token": "test-csrf-token"
    }, headers=headers, follow_redirects=True)
    assert create_resp.status_code == 200

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT employee_id FROM employees WHERE employee_code = %s", (emp_code,))
        row = cur.fetchone()
        assert row is not None
        emp_id = row[0]

        # 4. View Profile GET
        prof_resp = client.get(f"/admin/employees/profile/{emp_id}", headers=headers)
        assert prof_resp.status_code == 200
        prof_html = prof_resp.get_data(as_text=True)
        assert "Rohan Sharma" in prof_html
        assert emp_code in prof_html

        # 5. Edit Employee GET & POST
        edit_get = client.get(f"/admin/employees/edit/{emp_id}", headers=headers)
        assert edit_get.status_code == 200

        edit_post = client.post(f"/admin/employees/edit/{emp_id}", data={
            "employee_code": emp_code,
            "first_name": "Rohan",
            "last_name": "Verma",
            "email": "rohan.verma@muthoot.com",
            "phone": "+91 9988776655",
            "employment_status": "Active",
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert edit_post.status_code == 200

        cur.execute("SELECT last_name, email FROM employees WHERE employee_id = %s", (emp_id,))
        erow = cur.fetchone()
        assert erow[0] == "Verma"
        assert erow[1] == "rohan.verma@muthoot.com"

        # 6. Deactivate status toggle POST
        toggle_resp = client.post(f"/admin/employees/deactivate/{emp_id}", data={
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert toggle_resp.status_code == 200

        cur.execute("SELECT employment_status FROM employees WHERE employee_id = %s", (emp_id,))
        assert cur.fetchone()[0] == "Inactive"

        # Clean up
        cur.execute("DELETE FROM employees WHERE employee_id = %s", (emp_id,))
        conn.commit()
    finally:
        conn.close()


def test_admin_hierarchy_views_and_update():
    client = app.test_client()
    headers = login_client(client, user_id=3, role_name="Human Resources", employee_id=3)

    # 1. Hierarchy GET
    resp = client.get("/admin/hierarchy", headers=headers)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Employee Hierarchy" in html
    assert "Staff Reporting Directory" in html

    # 2. Hierarchy update POST
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT employee_id, manager_id FROM employees WHERE employee_id = 1")
        row = cur.fetchone()
        orig_manager = row[1] if row else None

        update_resp = client.post("/admin/hierarchy/update/1", data={
            "manager_id": "2",
            "csrf_token": "test-csrf-token"
        }, headers=headers, follow_redirects=True)
        assert update_resp.status_code == 200

        cur.execute("SELECT manager_id FROM employees WHERE employee_id = 1")
        assert cur.fetchone()[0] == 2

        # Restore original
        cur.execute("UPDATE employees SET manager_id = %s WHERE employee_id = 1", (orig_manager,))
        conn.commit()
    finally:
        conn.close()


def test_manager_appraisal_view_and_submission():
    client = app.test_client()
    headers = login_client(client, user_id=2, role_name="Manager", employee_id=2)

    # 1. GET appraisal page
    resp = client.get("/manager/appraisal", headers=headers)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Manager Performance Appraisal" in html
    assert "Productivity" in html
    assert "Quality of Work" in html

    # 2. POST submit appraisal
    post_resp = client.post("/manager/appraisal", data={
        "employee_id": 1,
        "manager_id": 2,
        "cycle_name": "Annual 2026",
        "productivity": 24,
        "quality": 19,
        "teamwork": 14,
        "communication": 9,
        "problem_solving": 9,
        "initiative": 8,
        "compliance": 9,
        "manager_comments": "Outstanding performance across enterprise goals.",
        "csrf_token": "test-csrf-token"
    }, headers=headers, follow_redirects=True)
    assert post_resp.status_code == 200

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT appraisal_id, total_score, status 
            FROM manager_appraisal 
            WHERE employee_id = 1 AND manager_id = 2 
            ORDER BY created_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        assert row is not None
        assert float(row[1]) == 92.0
        assert row[2] == "Submitted"

        # Clean up created appraisal record
        cur.execute("DELETE FROM manager_appraisal WHERE appraisal_id = %s", (row[0],))
        conn.commit()
    finally:
        conn.close()


def test_security_authorization_checks():
    client = app.test_client()

    # 1. Unauthenticated redirects to login
    anon_resp = client.get("/admin/employees")
    assert anon_resp.status_code in (302, 401)

    # 2. Employee cannot access Admin/HR routes
    emp_headers = login_client(client, user_id=1, role_name="Employee", employee_id=1)
    forbidden_resp = client.get("/admin/employees", headers=emp_headers)
    assert forbidden_resp.status_code == 403

    forbidden_mgr = client.get("/manager/appraisal", headers=emp_headers)
    assert forbidden_mgr.status_code == 403
