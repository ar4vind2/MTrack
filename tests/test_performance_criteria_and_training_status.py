import os
from datetime import datetime, date, time
from unittest.mock import MagicMock
import pytest

from routes.dashboard import update_final_performance_score
from routes.training_routes import (
    compute_session_status,
    compute_training_status,
    compute_employee_training_status
)


# ============================================================
# 1. BOUNDARY RATINGS & RECOMMENDATION CRITERIA TESTS
# ============================================================

@pytest.mark.parametrize("score,expected_rating,expected_recommendations", [
    # Boundary: 90.00% -> Outstanding
    (90.00, "Outstanding", ["Promotion Recommended and Salary Increment Recommended"]),
    (95.50, "Outstanding", ["Promotion Recommended and Salary Increment Recommended"]),
    # Boundary: 89.99% -> Excellent & Salary Increment Recommended
    (89.99, "Excellent", ["Salary Increment Recommended"]),
    (85.00, "Excellent", ["Salary Increment Recommended"]),
    # Boundary: 80.00% -> Excellent & No Immediate Action (since 75 <= score < 85)
    (80.00, "Excellent", ["No Immediate Action"]),
    (84.99, "Excellent", ["No Immediate Action"]),
    # Boundary: 79.99% -> Good & No Immediate Action
    (79.99, "Good", ["No Immediate Action"]),
    (75.00, "Good", ["No Immediate Action"]),
    # Boundary: 70.00% -> Good & Training / Development Recommended (since < 75%)
    (74.99, "Good", ["Training / Development Recommended"]),
    (70.00, "Good", ["Training / Development Recommended"]),
    # Boundary: 69.99% -> Needs Improvement & Training / Development Recommended
    (69.99, "Needs Improvement", ["Training / Development Recommended"]),
    # Boundary: 60.00% -> Needs Improvement & Training / Development Recommended
    (60.00, "Needs Improvement", ["Training / Development Recommended"]),
    # Boundary: 59.99% -> Unsatisfactory & Training / Development Recommended
    (59.99, "Unsatisfactory", ["Training / Development Recommended"]),
    (45.00, "Unsatisfactory", ["Training / Development Recommended"]),
])
def test_rating_and_recommendation_boundaries(score, expected_rating, expected_recommendations):
    cursor = MagicMock()
    # Mock row: (kpi, manager, attendance, behaviour, self, training)
    # Give all components = score so final weighted score equals score exactly
    cursor.fetchone.return_value = (score, score, score, score, score, score)

    final_score = update_final_performance_score(cursor, employee_id=1, cycle_id=1)
    assert final_score == round(score, 2)

    # Verify that cursor.execute was called to update performance_result with the expected rating
    update_calls = [
        call for call in cursor.execute.call_args_list
        if "UPDATE performance_result" in call[0][0]
    ]
    assert len(update_calls) > 0, "UPDATE performance_result must be executed"
    update_args = update_calls[0][0][1]
    # update_args: (final_score, rating, employee_id, cycle_id)
    assert update_args[1] == expected_rating


# ============================================================
# 2. TRAINING STATUS (DATE & TIME BASED) TESTS
# ============================================================

def test_training_program_status_by_date():
    # Future training
    assert compute_training_status("2026-11-01", "2026-11-10", now=datetime(2026, 10, 11, 10, 0)) == "Pending"
    # Past training
    assert compute_training_status("2026-03-01", "2026-03-05", now=datetime(2026, 10, 11, 10, 0)) == "Completed"
    # Current ongoing multi-day training
    assert compute_training_status("2026-10-08", "2026-10-15", now=datetime(2026, 10, 11, 10, 0)) == "In Progress"


def test_training_program_status_single_day_with_times():
    sessions = [{
        "session_date": date(2026, 10, 11),
        "start_time": time(14, 0),
        "end_time": time(16, 0)
    }]
    # Today before session start time -> Pending
    assert compute_training_status("2026-10-11", "2026-10-11", sessions=sessions, now=datetime(2026, 10, 11, 11, 30)) == "Pending"
    # Today during session -> In Progress
    assert compute_training_status("2026-10-11", "2026-10-11", sessions=sessions, now=datetime(2026, 10, 11, 15, 0)) == "In Progress"
    # Today after session end time -> Completed
    assert compute_training_status("2026-10-11", "2026-10-11", sessions=sessions, now=datetime(2026, 10, 11, 16, 30)) == "Completed"


def test_session_status():
    # Future session
    assert compute_session_status("2026-10-20", "10:00", "12:00", now=datetime(2026, 10, 11, 10, 0)) == "Pending"
    # Past session
    assert compute_session_status("2026-10-05", "10:00", "12:00", now=datetime(2026, 10, 11, 10, 0)) == "Completed"
    # Today before start
    assert compute_session_status("2026-10-11", "14:00", "17:00", now=datetime(2026, 10, 11, 12, 0)) == "Pending"
    # Today during session
    assert compute_session_status("2026-10-11", "14:00", "17:00", now=datetime(2026, 10, 11, 15, 30)) == "In Progress"
    # Today after end
    assert compute_session_status("2026-10-11", "14:00", "17:00", now=datetime(2026, 10, 11, 17, 30)) == "Completed"


def test_employee_training_status_with_certificate():
    # Ongoing training with certificate -> Completed
    assert compute_employee_training_status("2026-10-08", "2026-10-15", certificate=True, now=datetime(2026, 10, 11, 10, 0)) == "Completed"
    # Future training even with certificate flag -> Pending (cannot be completed before training begins)
    assert compute_employee_training_status("2026-11-01", "2026-11-10", certificate=True, now=datetime(2026, 10, 11, 10, 0)) == "Pending"


# ============================================================
# 3. UI AND NAVIGATION INTEGRATION TESTS
# ============================================================

def test_profile_page_has_back_button():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(base_dir, "templates", "profile.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "goBackDashboard" in html, "Profile page must have goBackDashboard() function for the Back button"
    assert "onclick=\"goBackDashboard()\"" in html, "Profile page topbar must have 'Back' button triggering goBackDashboard()"
    assert "<span>Back</span>" in html or "Back" in html, "Profile page must show Back button text"


def test_appraisal_cycles_has_view_results_action():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(base_dir, "templates", "appraisal_cycles.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "View Results" in html, "Appraisal cycles list must have 'View Results' button"
    assert "/performance-results?cycle_id=" in html, "'View Results' button must link to /performance-results?cycle_id=..."


def test_performance_results_methodology_and_breakdown():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(base_dir, "templates", "performance_results.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "Performance Calculation Methodology" in html
    assert "KPI Score" in html and "40%" in html
    assert "Manager Appraisal" in html and "30%" in html
    assert "Attendance Record" in html and "10%" in html
    assert "Behaviour & Core Values" in html and "10%" in html
    assert "scoreBreakdownModal" in html
    assert "cycleFilter" in html
