import io
import os
import pytest
from app import app
from config import get_db_connection


def login_client(client, user_id=6, role_name="Employee", employee_id=5):
    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-csrf-token"
        sess["user_id"] = user_id
        sess["role_name"] = role_name
        if employee_id:
            sess["employee_id"] = employee_id
    return {"X-CSRF-Token": "test-csrf-token"}


def test_appraisal_form_renders_certificate_inputs():
    client = app.test_client()
    login_client(client, user_id=6, role_name="Employee", employee_id=5)

    response = client.get("/appraisal-form")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Verify form has multipart enctype
    assert 'enctype="multipart/form-data"' in html
    # Verify certificate file input and fields
    assert 'name="certificate_file"' in html
    assert 'name="certificate_name"' in html
    assert 'name="certificate_issue_date"' in html
    assert 'accept=".pdf,.png,.jpg,.jpeg"' in html


def test_appraisal_form_rejects_disallowed_file_type():
    client = app.test_client()
    headers = login_client(client, user_id=6, role_name="Employee", employee_id=5)

    bad_file = (io.BytesIO(b"malicious executable content"), "script.exe")

    form_data = {
        "cycle_id": "1",
        "achievements": "Tested invalid certificate upload rejection.",
        "challenges": "None",
        "certifications": "Invalid Ext Test",
        "training_completed": "Security Awareness",
        "future_goals": "Security Auditor",
        "suggestions": "None",
        "certificate_file": bad_file,
        "csrf_token": "test-csrf-token"
    }

    response = client.post("/appraisal-form", data=form_data, headers=headers, content_type="multipart/form-data")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Invalid certificate file type" in html


def test_appraisal_submission_with_certificate_upload():
    # Employee 5 (Akhil Thomas, user_id=6, manager_id=1)
    client = app.test_client()
    headers = login_client(client, user_id=6, role_name="Employee", employee_id=5)

    # Create dummy PDF file
    pdf_content = b"%PDF-1.4 test certificate document for automated test"
    pdf_file = (io.BytesIO(pdf_content), "AWS_Certified_Architect.pdf")

    form_data = {
        "cycle_id": "1",
        "achievements": "Delivered mission-critical cloud architecture.",
        "challenges": "Distributed state synchronization.",
        "certifications": "AWS Solutions Architect Professional",
        "training_completed": "Advanced Cloud Systems",
        "future_goals": "Cloud Solutions Director",
        "suggestions": "Adopt micro-frontends",
        "overall_self_rating": "5",
        "certificate_name": "AWS Solutions Architect",
        "certificate_issue_date": "2026-05-15",
        "certificate_file": pdf_file,
        "csrf_token": "test-csrf-token"
    }

    response = client.post("/appraisal-form", data=form_data, headers=headers, content_type="multipart/form-data")
    assert response.status_code == 302
    assert "/self-appraisal" in response.headers["Location"]

    # Verify database insertion in certifications table
    conn = get_db_connection()
    cert_id = None
    saved_file_path = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT certification_id, employee_id, certification_name, file_name, file_path, file_type, issued_date
            FROM certifications
            WHERE employee_id = 5 AND certification_name = 'AWS Solutions Architect'
            ORDER BY uploaded_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        assert row is not None
        cert_id = row[0]
        assert row[1] == 5
        assert row[2] == "AWS Solutions Architect"
        assert "AWS_Certified_Architect.pdf" in row[3]
        assert row[5] == "PDF"
        assert str(row[6]) == "2026-05-15"

        saved_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static",
            row[4]
        )
        assert os.path.exists(saved_file_path)

        # Also verify self_appraisal record exists
        cur.execute("SELECT self_score FROM self_appraisal WHERE employee_id = 5 AND cycle_id = 1 ORDER BY created_at DESC LIMIT 1")
        sa_row = cur.fetchone()
        assert sa_row is not None
        assert float(sa_row[0]) == 100.0

    finally:
        conn.close()

    # Verify employee can see their certificate on /self-appraisal
    self_appr_resp = client.get("/self-appraisal")
    assert self_appr_resp.status_code == 200
    self_appr_html = self_appr_resp.get_data(as_text=True)
    assert "AWS Solutions Architect" in self_appr_html
    assert "View Certificate" in self_appr_html

    # Now verify manager can view the uploaded certificate
    # Manager is user_id=2, employee_id=1
    mgr_client = app.test_client()
    login_client(mgr_client, user_id=2, role_name="Manager", employee_id=1)

    # 1. Review employee appraisal detail page for employee 5
    detail_resp = mgr_client.get("/review-employee-appraisal/5")
    assert detail_resp.status_code == 200
    detail_html = detail_resp.get_data(as_text=True)
    assert "AWS Solutions Architect" in detail_html
    assert "View Certificate" in detail_html
    assert f"/appraisal/certificate/{cert_id}" in detail_html

    # 2. Review summary list page shows certificate indicator
    list_resp = mgr_client.get("/review-appraisal")
    assert list_resp.status_code == 200
    list_html = list_resp.get_data(as_text=True)
    assert "Cert" in list_html

    # 3. Dedicated certificate viewing endpoint as manager
    cert_resp = mgr_client.get(f"/appraisal/certificate/{cert_id}")
    assert cert_resp.status_code == 200
    assert cert_resp.data == pdf_content

    # 4. Employee viewing own certificate endpoint
    emp_cert_resp = client.get(f"/appraisal/certificate/{cert_id}")
    assert emp_cert_resp.status_code == 200
    assert emp_cert_resp.data == pdf_content

    # 5. Unauthorized employee viewing certificate
    unauth_client = app.test_client()
    login_client(unauth_client, user_id=8, role_name="Employee", employee_id=7)
    unauth_resp = unauth_client.get(f"/appraisal/certificate/{cert_id}")
    assert unauth_resp.status_code == 403

    # Clean up test artifact from disk and db
    if saved_file_path and os.path.exists(saved_file_path):
        try:
            os.remove(saved_file_path)
        except Exception:
            pass

    clean_conn = get_db_connection()
    try:
        cur = clean_conn.cursor()
        cur.execute("DELETE FROM certifications WHERE certification_id = %s", (cert_id,))
        clean_conn.commit()
    finally:
        clean_conn.close()
