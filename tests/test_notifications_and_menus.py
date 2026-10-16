import pytest
from app import app
from config import get_db_connection

def test_manager_api_returns_notifications():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['username'] = 'manager_it'
        sess['role_id'] = 2
        sess['role_name'] = 'Manager'
        sess['employee_id'] = 1

    resp = client.get('/manager')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('success') is True
    assert 'notifications' in data
    assert isinstance(data['notifications'], list)

def test_notifications_endpoint_for_manager():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 3
        sess['username'] = 'manager_hr'
        sess['role_id'] = 2
        sess['role_name'] = 'Manager'
        sess['employee_id'] = 2

    resp = client.get('/api/notifications/')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('success') is True
    assert len(data.get('notifications', [])) >= 1

def test_mark_all_notifications_read():
    client = app.test_client()
    # Get CSRF token
    csrf_resp = client.get('/api/csrf-token')
    csrf_token = csrf_resp.get_json().get('csrf_token')

    with client.session_transaction() as sess:
        sess['user_id'] = 3
        sess['username'] = 'manager_hr'
        sess['role_id'] = 2
        sess['role_name'] = 'Manager'
        sess['employee_id'] = 2
        sess['_csrf_token'] = csrf_token

    resp = client.post('/api/notifications/read-all', headers={'X-CSRF-Token': csrf_token})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('success') is True

def test_sidebar_menus_in_static_html():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'admin'
        sess['role_id'] = 1
        sess['role_name'] = 'HR Admin'

    # Check HR dashboard has Organization & Staff
    resp = client.get('/hr-dashboard')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Organization & Staff' in html
    assert '/admin/employees' in html
    assert '/admin/hierarchy' in html
    assert '/admin/departments' in html
    assert '/admin/branches' in html
    assert '/admin/designations' in html
    assert '/admin/users' in html

    # Check manager templates have Manager Appraisal
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['username'] = 'manager_it'
        sess['role_id'] = 2
        sess['role_name'] = 'Manager'
        sess['employee_id'] = 1

    resp_mgr = client.get('/manager-dashboard')
    assert resp_mgr.status_code == 200
    mgr_html = resp_mgr.get_data(as_text=True)
    assert '/manager/appraisal' in mgr_html

    resp_team = client.get('/team-evaluation')
    assert resp_team.status_code == 200
    team_html = resp_team.get_data(as_text=True)
    assert '/manager/appraisal' in team_html
    assert 'Self Service' in team_html
    assert '/my-appraisals' in team_html
    assert '/self-appraisal' in team_html


def test_manager_assignment_dropdown_only_shows_managers():
    """Verify that manager dropdowns in Add Employee, Edit Employee, and Hierarchy only show managers."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'admin'
        sess['role_id'] = 1
        sess['role_name'] = 'HR Admin'
        sess['employee_id'] = 1

    # 1. Add Employee GET
    resp_add = client.get('/admin/employees/add')
    assert resp_add.status_code == 200
    html_add = resp_add.get_data(as_text=True)

    # Managers should appear
    assert "Rahul Menon" in html_add
    assert "Anjali Nair" in html_add
    assert "Arun Kumar" in html_add

    # Regular employees should NOT appear in reporting manager options
    # Non-managers: Akhil Thomas (EMP005), Meera Joseph (EMP006), Neha Krishnan (EMP007), Sandeep Pillai (EMP008)
    assert 'value="5">Akhil Thomas' not in html_add
    assert 'value="6">Meera Joseph' not in html_add
    assert 'value="7">Neha Krishnan' not in html_add
    assert 'value="8">Sandeep Pillai' not in html_add

    # 2. Edit Employee GET
    resp_edit = client.get('/admin/employees/edit/5')
    assert resp_edit.status_code == 200
    html_edit = resp_edit.get_data(as_text=True)
    assert 'value="5">Akhil Thomas' not in html_edit
    assert 'value="6">Meera Joseph' not in html_edit

    # 3. Hierarchy GET
    resp_hier = client.get('/admin/hierarchy')
    assert resp_hier.status_code == 200
    html_hier = resp_hier.get_data(as_text=True)
    # Check options inside select name="manager_id"
    assert "Rahul Menon" in html_hier
    assert 'Akhil Thomas (EMP005' not in html_hier  # should not be inside select options


def test_notification_deduplication_and_safe_creation():
    """Verify that notifications endpoint deduplicates identical items and create_notification avoids duplicates."""
    from routes.notifications import create_notification

    # Create two duplicate unread notifications
    test_user_id = 4
    t_title = "Test Unique Alert"
    t_msg = "This is a duplicate test notification message."

    created1 = create_notification(test_user_id, t_title, t_msg, "system")
    assert created1 is True

    # Attempt to insert identical unread notification again
    created2 = create_notification(test_user_id, t_title, t_msg, "system")
    assert created2 is True

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = test_user_id
        sess['username'] = 'vishnu_tl'
        sess['role_id'] = 4
        sess['role_name'] = 'Team Leader'
        sess['employee_id'] = 4

    resp = client.get('/api/notifications/')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('success') is True

    matching = [n for n in data.get('notifications', []) if n.get('title') == t_title and n.get('message') == t_msg]
    assert len(matching) == 1, f"Expected exactly 1 notification, found {len(matching)}"
