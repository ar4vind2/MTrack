from routes.dashboard import calculate_leave_balances, get_leave_category


def test_leave_balances_only_deduct_approved_usage_from_matching_category():
    balances = calculate_leave_balances({
        "casual leave": 3,
        "sick leave": 2,
    }, {
        "casual leave": 8,
        "sick leave": 6,
        "annual privilege leave": 12,
    })
    balances_by_name = {
        balance["name"]: balance
        for balance in balances
    }

    assert balances_by_name["Casual Leave"]["remaining_days"] == 5
    assert balances_by_name["Sick Leave"]["remaining_days"] == 4
    assert balances_by_name["Annual Privilege Leave"]["remaining_days"] == 12


def test_leave_categories_default_to_zero_without_department_totals():
    balances = calculate_leave_balances({})

    assert all(balance["total_days"] == 0 for balance in balances)
    assert all(balance["remaining_days"] == 0 for balance in balances)


def test_leave_category_lookup_is_case_and_whitespace_insensitive():
    assert get_leave_category("  sick LEAVE ")["code"] == "SL"
