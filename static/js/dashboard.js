/* ==========================================================================
   MUTHOOT FINANCE EMPLOYEE APPRAISAL SYSTEM - DASHBOARD CONTROLLER (MEMBER 6)
   ApexCharts Integration, PDF/Excel Report Exports, Notifications Engine
   ========================================================================== */

// --- GLOBAL STATE & MOCK DATA ---
const systemState = {
    currentRole: 'employee',
    notifications: [
        { id: 1, type: 'appraisal', title: 'Self-Appraisal Submitted', desc: 'Your Q2 2026 self-appraisal form was submitted to Manager.', time: '10 mins ago', unread: true },
        { id: 2, type: 'training', title: 'Mandatory Compliance Training', desc: 'Anti-Money Laundering (AML) 2026 module assigned.', time: '2 hours ago', unread: true },
        { id: 3, type: 'system', title: 'Appraisal Cycle Q2 2026 Active', desc: 'HR has activated the Q2 performance cycle for all branches.', time: '1 day ago', unread: false },
        { id: 4, type: 'appraisal', title: 'Manager Rating Complete', desc: 'Rajesh Nair completed your Q1 evaluation score (4.5 ⭐).', time: '3 days ago', unread: false }
    ]
};

let csrfTokenPromise = null;

async function getCsrfToken() {
    if (!csrfTokenPromise) {
        csrfTokenPromise = fetch('/api/csrf-token', {
            credentials: 'same-origin'
        }).then(async (response) => {
            const data = await response.json();

            if (!response.ok || !data.csrf_token) {
                throw new Error('Unable to initialise a secure request.');
            }

            return data.csrf_token;
        }).catch((error) => {
            csrfTokenPromise = null;
            throw error;
        });
    }

    return csrfTokenPromise;
}

// Mock data per role
const roleData = {
    employee: {
        name: "Arjun Kumar",
        roleTitle: "Software Executive",
        department: "Information Technology",
        branch: "Kochi Branch",
        avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=100",
        stats: { overallScore: "4.5 / 5", attendance: "94%", goalsCompleted: "88%", trainingStatus: "Completed" }
    },
    manager: {
        name: "Rajesh Nair",
        roleTitle: "IT Branch Manager",
        department: "Information Technology",
        branch: "Kochi Branch",
        avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&q=80&w=100",
        stats: { teamAverage: "0", pendingReviews: "0", completedReviews: "0", totalEmployees: "0" }
    },
    hr: {
        name: "Sunitha Varma",
        roleTitle: "Head of Human Resources",
        department: "Human Resources",
        branch: "Head Office",
        avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=100",
        stats: { totalEmployees: "560", avgRating: "4.3", completedAppraisals: "510", pendingReviews: "50" }
    }
};

// --- SIDEBAR TOGGLE & RESPONSIVE ENGINE ---
function toggleSidebar() {
    if (window.innerWidth < 992) {
        document.body.classList.toggle('mobile-sidebar-open');
    } else {
        document.body.classList.toggle('sidebar-collapsed');
    }

    // Trigger window resize event so ApexCharts resize smoothly
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 320);
}

function closeMobileSidebar() {
    document.body.classList.remove('mobile-sidebar-open');
}

// --- CHART INSTANCES HOLDER ---
const chartInstances = {};

// Helper to safely render ApexCharts
function renderSafeChart(key, elementId, options) {
    const el = document.querySelector(elementId);
    if (!el) return;

    if (chartInstances[key]) {
        try {
            chartInstances[key].destroy();
        } catch (e) {
            console.warn(`Error destroying chart ${key}:`, e);
        }
        delete chartInstances[key];
    }

    if (!el.style.minHeight) el.style.minHeight = "250px";

    try {
        chartInstances[key] = new ApexCharts(el, options);
        chartInstances[key].render();
    } catch (err) {
        console.error(`Failed rendering ApexChart ${key}:`, err);
    }
}

// ============================================================
// EMPLOYEE DASHBOARD - REAL DATABASE DATA
// ============================================================

let employeeDashboardData = null;
let employeeDashboardLoading = false;

function initEmployeeApexCharts(data = employeeDashboardData) {

    if (!data) {
        console.warn("Employee dashboard data is not available yet.");
        return;
    }

    const performance = data.performance || {};
    const attendance = data.attendance || {};
    const kra = data.kra || {};
    const trend = data.performance_trend || [];

    // ========================================================
    // 1. PERFORMANCE TREND
    // ========================================================

    renderSafeChart('empTrend', '#empTrendChart', {

        series: [
            {
                name: "Performance Score",
                data: trend.map(item => Number(item.score || 0))
            }
        ],

        chart: {
            type: 'line',
            height: 260,
            toolbar: {
                show: false
            },
            zoom: {
                enabled: false
            }
        },

        colors: ['#C8102E'],

        stroke: {
            curve: 'smooth',
            width: 2.5
        },

        markers: {
            size: 4,
            colors: ['#D4AF37'],
            strokeColors: '#FFFFFF',
            strokeWidth: 2
        },

        xaxis: {
            categories: trend.map(item => String(item.year))
        },

        yaxis: {
            min: 0,
            max: 100,
            tickAmount: 5
        },

        grid: {
            borderColor: '#E5E7EB',
            strokeDashArray: 3
        },

        tooltip: {
            theme: 'light',

            y: {
                formatter: function(value) {
                    return Number(value).toFixed(2) + '%';
                }
            }
        }
    });


    // ========================================================
    // 2. ATTENDANCE PIE CHART
    // ========================================================

    const present = Number(attendance.present || 0);
    const absent = Number(attendance.absent || 0);
    const leave = Number(attendance.leave || 0);

    renderSafeChart('empAttendance', '#empAttendanceChart', {

        series: [
            present,
            absent + leave
        ],

        chart: {
            type: 'pie',
            height: 220
        },

        labels: [
            'Present Days',
            'Leave / Absent'
        ],

        colors: [
            '#137333',
            '#C8102E'
        ],

        legend: {
            position: 'bottom',
            fontSize: '11px',
            fontFamily: 'Poppins'
        },

        dataLabels: {
            enabled: true,

            formatter: function(value) {
                return value.toFixed(0) + '%';
            }
        }
    });


    // ========================================================
    // 3. KRA COMPLETION RADIAL CHART
    // ========================================================

    const kraCompletion =
        Number(kra.completion_percentage || 0);

    renderSafeChart('empGoalRadial', '#empGoalRadialChart', {

        series: [
            kraCompletion
        ],

        chart: {
            type: 'radialBar',
            height: 230
        },

        plotOptions: {

            radialBar: {

                hollow: {
                    size: '65%'
                },

                track: {
                    background: '#F3F4F6'
                },

                dataLabels: {

                    name: {
                        show: true,
                        label: 'KRA Goals',
                        color: '#6B7280',
                        fontSize: '12px'
                    },

                    value: {
                        show: true,
                        fontSize: '22px',
                        fontWeight: '700',
                        color: '#C8102E',

                        formatter: function(value) {
                            return Number(value).toFixed(0) + '%';
                        }
                    }
                }
            }
        },

        colors: [
            '#D4AF37'
        ]
    });
}
// ============================================================
// LOAD EMPLOYEE DASHBOARD DATA FROM FLASK
// ============================================================

async function loadEmployeeDashboardData() {

    if (employeeDashboardLoading) {
        return;
    }

    employeeDashboardLoading = true;

    try {

        const response = await fetch(
            '/employee',
            {
                method: 'GET',

                credentials: 'same-origin',

                headers: {
                    'Accept': 'application/json'
                }
            }
        );


        const data = await response.json();


        // Check Flask response

        if (!response.ok || !data.success) {

            throw new Error(
                data.message ||
                'Unable to load employee dashboard data.'
            );
        }


        // Save API response

        employeeDashboardData = data;


        // ====================================================
        // UPDATE ROLE DATA
        // ====================================================

        const employee = data.employee || {};

        roleData.employee.name =
            employee.name || 'Employee';

        roleData.employee.roleTitle =
            employee.designation || 'Employee';

        roleData.employee.department =
            employee.department || 'Not Assigned';


        roleData.employee.stats = {

            overallScore:
                Number(
                    data.performance?.final_score || 0
                ).toFixed(2) + '%',

            attendance:
                Number(
                    data.attendance?.percentage || 0
                ).toFixed(2) + '%',

            goalsCompleted:
                Number(
                    data.kra?.completion_percentage || 0
                ).toFixed(2) + '%',

            trainingStatus:
                Number(
                    data.training?.completed || 0
                ) > 0
                    ? 'Completed'
                    : 'Pending'
        };

        // ====================================================
        // UPDATE HTML
        // ====================================================

        updateEmployeeDashboardUI(data);


        // ====================================================
        // UPDATE NOTIFICATIONS
        // ====================================================

        renderNotificationsFromAPI(
            data.notifications || []
        );


        // ====================================================
        // UPDATE CHARTS
        // ====================================================

        initEmployeeApexCharts(data);


    } catch (error) {

        console.error(
            'EMPLOYEE DASHBOARD LOAD ERROR:',
            error
        );

        showDashboardError(
            error.message
        );

    } finally {

        employeeDashboardLoading = false;
    }
}
// ============================================================
// MANAGER DASHBOARD - REAL DATABASE DATA
// ============================================================

let managerDashboardData = null;
let managerDashboardLoading = false;


async function loadManagerDashboardData() {

    if (managerDashboardLoading) {
        return;
    }

    managerDashboardLoading = true;

    try {

        const response = await fetch(
            '/manager',
            {
                method: 'GET',

                credentials: 'same-origin',

                headers: {
                    'Accept': 'application/json'
                }
            }
        );


        const data = await response.json();


        if (!response.ok || !data.success) {

            throw new Error(
                data.message ||
                'Unable to load manager dashboard data.'
            );
        }


        // Save API response

        managerDashboardData = data;


        // Update manager dashboard

        updateManagerDashboardUI(data);


        // Render real charts

        initManagerApexCharts(data);


    } catch (error) {

        console.error(
            'MANAGER DASHBOARD LOAD ERROR:',
            error
        );

    } finally {

        managerDashboardLoading = false;

    }
}

function updateManagerDashboardUI(data) {
    const manager =
        data.manager || {};

    const summary =
        data.summary || {};
    updateManagerAppraisalTable(
        data.appraisal_reviews || []
    );

    // ========================================================
    // TOPBAR
    // ========================================================

    const welcomeName =
        document.getElementById('welcomeName');

    const welcomeRole =
        document.getElementById('welcomeRole');

    const userBadgeName =
        document.getElementById('userBadgeName');

    const userBadgeRole =
        document.getElementById('userBadgeRole');


    if (welcomeName) {

        welcomeName.textContent =
            manager.name || 'Manager';
    }


    if (welcomeRole) {

        welcomeRole.textContent =
            `(${manager.designation || 'Manager'})`;
    }


    if (userBadgeName) {

        userBadgeName.textContent =
            manager.name || 'Manager';
    }


    if (userBadgeRole) {

        userBadgeRole.textContent =
            manager.department || 'Department';
    }


    // ========================================================
    // MANAGER STAT CARDS
    // ========================================================

    const statCards =
        document.querySelectorAll(
            '#manager-view .stat-card'
        );


    if (statCards.length >= 4) {

        const values = [

            Number(
                summary.team_average || 0
            ).toFixed(2) + '%',

            String(
                summary.pending_reviews || 0
            ),

            String(
                summary.completed_reviews || 0
            ),

            String(
                summary.total_employees || 0
            )
        ];


        values.forEach((value, index) => {

            const heading =
                statCards[index].querySelector('h2');

            if (heading) {
                heading.textContent = value;
            }

        });
    }
}
// ============================================================
// MANAGER APPRAISAL REVIEW TABLE
// ============================================================

function updateManagerAppraisalTable(reviews) {

    const tbody =
        document.querySelector(
            '#manager-view .table-muthoot tbody'
        );


    if (!tbody) {
        return;
    }


    // No appraisal records

    if (!reviews || reviews.length === 0) {

        tbody.innerHTML = `
            <tr>
                <td colspan="6"
                    class="text-center text-muted py-4">

                    No appraisal records found.

                </td>
            </tr>
        `;

        return;
    }


    tbody.innerHTML =
        reviews.map(review => {

            const selfScore =
                Number(
                    review.self_score || 0
                ).toFixed(2);


            const managerScore =
                Number(
                    review.manager_score || 0
                ).toFixed(2);


            let statusClass =
                'pending';


            if (
                review.status === 'Approved'
            ) {

                statusClass =
                    'approved';

            }
            else if (
                review.status === 'Submitted'
            ) {

                statusClass =
                    'submitted';

            }


            const actionButton =
                review.status === 'Approved'

                    ? `
                        <button
                            class="btn btn-sm btn-outline-muthoot"
                            onclick="viewManagerAppraisal(${review.appraisal_id})">

                            View

                        </button>
                      `

                    : `
                        <button
                            class="btn btn-sm btn-muthoot"
                            onclick="evaluateManagerAppraisal(${review.appraisal_id})">

                            Evaluate

                        </button>
                      `;


            return `

                <tr>

                    <td>

                        <strong>
                            ${escapeHTML(
                                review.employee_name
                            )}
                        </strong>

                        <br>

                        <small class="text-muted">
                            ${escapeHTML(
                                review.employee_code
                            )}
                        </small>

                    </td>


                    <td>

                        ${escapeHTML(
                            review.department
                        )}

                    </td>


                    <td>

                        ${selfScore} / 5

                    </td>


                    <td>

                        <span class="rating-pill">

                            ${managerScore}

                            ⭐

                        </span>

                    </td>


                    <td>

                        <span
                            class="badge-muthoot ${statusClass}">

                            ${escapeHTML(
                                review.status ||
                                'Pending'
                            )}

                        </span>

                    </td>


                    <td>

                        ${actionButton}

                    </td>

                </tr>

            `;

        }).join('');
}
function evaluateManagerAppraisal(
    appraisalId
) {

    console.log(
        'Evaluate appraisal:',
        appraisalId
    );

    alert(
        `Evaluation page for appraisal ${appraisalId} will be connected next.`
    );
}


function viewManagerAppraisal(
    appraisalId
) {

    console.log(
        'View appraisal:',
        appraisalId
    );

    alert(
        `Viewing appraisal ${appraisalId}.`
    );
}
// ============================================================
// UPDATE EMPLOYEE DASHBOARD UI
// ============================================================

function updateEmployeeDashboardUI(data) {

    const employee = data.employee || {};
    const performance = data.performance || {};
    const attendance = data.attendance || {};
    const kra = data.kra || {};
    const training = data.training || {};


    // ========================================================
    // TOPBAR
    // ========================================================

    const welcomeName =
        document.getElementById('welcomeName');

    const welcomeRole =
        document.getElementById('welcomeRole');

    const userBadgeName =
        document.getElementById('userBadgeName');

    const userBadgeRole =
        document.getElementById('userBadgeRole');


    if (welcomeName) {

        welcomeName.textContent =
            employee.name || 'Employee';
    }


    if (welcomeRole) {

        welcomeRole.textContent =
            `(${employee.designation || 'Employee'})`;
    }


    if (userBadgeName) {

        userBadgeName.textContent =
            employee.name || 'Employee';
    }


    if (userBadgeRole) {

        userBadgeRole.textContent =
            employee.department ||
            'Department Not Assigned';
    }


    // ========================================================
    // STAT CARDS
    // ========================================================

    const statCards =
        document.querySelectorAll(
            '#employee-view .stat-card'
        );


    if (statCards.length >= 4) {

        const score =
            statCards[0].querySelector('h2');

        const attendanceValue =
            statCards[1].querySelector('h2');

        const goalsValue =
            statCards[2].querySelector('h2');

        const trainingValue =
            statCards[3].querySelector('h2');


        // Overall Score

        if (score) {

            score.textContent =
                Number(
                    performance.final_score || 0
                ).toFixed(2) + '%';
        }


        // Attendance

        if (attendanceValue) {

            attendanceValue.textContent =
                Number(
                    attendance.percentage || 0
                ).toFixed(2) + '%';
        }


        // KRA completion

        if (goalsValue) {

            goalsValue.textContent =
                Number(
                    kra.completion_percentage || 0
                ).toFixed(2) + '%';
        }


        // Training

        if (trainingValue) {

            if (
                Number(training.completed || 0) > 0
            ) {

                trainingValue.innerHTML =
                    '<i class="bi bi-award-fill"></i> Completed';

            } else {

                trainingValue.innerHTML =
                    '<i class="bi bi-hourglass-split"></i> Pending';
            }
        }
    }


    // Update appraisal table

    updateEmployeeAppraisalSummary(data);
}
// ============================================================
// EMPLOYEE APPRAISAL SUMMARY
// ============================================================

function updateEmployeeAppraisalSummary(data) {

    const tbody =
        document.querySelector(
            '#employee-view .table-muthoot tbody'
        );


    if (!tbody) {
        return;
    }


    const performance =
        data.performance || {};


    const year =
        performance.year || '-';


    const score =
        performance.final_score !== null &&
        performance.final_score !== undefined

            ? Number(
                performance.final_score
              ).toFixed(2) + '%'

            : '-';


    const rating =
        performance.rating ||
        'Not Available';


    const recommendation =
        performance.recommendation ||
        'Not Available';


    tbody.innerHTML = `

        <tr>

            <td>
                ${year}
            </td>

            <td>
                <span class="rating-pill">
                    ${score}
                </span>
            </td>

            <td>
                System Calculated
            </td>

            <td>
                <span class="badge-muthoot completed">
                    ${escapeHTML(rating)}
                </span>
            </td>

            <td>
                ${escapeHTML(recommendation)}
            </td>

        </tr>

    `;
}
// ============================================================
// NOTIFICATIONS FROM FLASK
// ============================================================

function renderNotificationsFromAPI(notifications) {

    systemState.notifications =
        notifications.map(notification => ({

            id: notification.id,

            type:
                notification.type ||
                'system',

            title:
                notification.title ||
                'Notification',

            desc:
                notification.message ||
                '',

            time:
                formatNotificationTime(
                    notification.created_at
                ),

            unread:
                !notification.is_read
        }));


    renderNotifications();
}
function formatNotificationTime(createdAt) {

    if (!createdAt) {
        return '';
    }


    const date =
        new Date(createdAt);


    if (Number.isNaN(date.getTime())) {
        return '';
    }


    const seconds =
        Math.floor(
            (Date.now() - date.getTime()) / 1000
        );


    if (seconds < 60) {
        return 'Just now';
    }


    if (seconds < 3600) {

        return (
            Math.floor(seconds / 60) +
            ' mins ago'
        );
    }


    if (seconds < 86400) {

        return (
            Math.floor(seconds / 3600) +
            ' hours ago'
        );
    }


    return (
        Math.floor(seconds / 86400) +
        ' days ago'
    );
}
function escapeHTML(value) {

    return String(value ?? '')

        .replace(/&/g, '&amp;')

        .replace(/</g, '&lt;')

        .replace(/>/g, '&gt;')

        .replace(/"/g, '&quot;')

        .replace(/'/g, '&#039;');
}
function showDashboardError(message) {

    console.error(message);


    const employeeView =
        document.getElementById(
            'employee-view'
        );


    if (!employeeView) {
        return;
    }


    let errorBox =
        document.getElementById(
            'dashboardApiError'
        );


    if (!errorBox) {

        errorBox =
            document.createElement('div');

        errorBox.id =
            'dashboardApiError';

        errorBox.className =
            'alert alert-danger mb-4';

        employeeView.prepend(
            errorBox
        );
    }


    errorBox.innerHTML =
        `<strong>
            Unable to load dashboard data.
        </strong>
        <br>
        ${escapeHTML(message)}`;
}

function initManagerApexCharts(data) {

    if (!data) {
        return;
    }


    const distribution =
        data.performance_distribution || {};

    const competencies =
        data.competencies || {};

    const team =
        data.team_performance || [];

    const summary =
        data.summary || {};


    // ========================================================
    // 1. TEAM PERFORMANCE
    // ========================================================

    renderSafeChart(
        'mgrDeptBar',
        '#mgrDeptChart',
        {

            series: [
                {
                    name: 'Performance Score (%)',

                    data: team.map(
                        employee =>
                            Number(employee.score || 0)
                    )
                }
            ],

            chart: {
                type: 'bar',
                height: 260,
                toolbar: {
                    show: false
                }
            },

            colors: ['#C8102E'],

            plotOptions: {
                bar: {
                    borderRadius: 5,
                    columnWidth: '40%'
                }
            },

            xaxis: {
                categories: team.map(
                    employee =>
                        employee.employee_code
                )
            },

            yaxis: {
                min: 0,
                max: 100
            },

            grid: {
                borderColor: '#E5E7EB',
                strokeDashArray: 3
            }
        }
    );


    // ========================================================
    // 2. PERFORMANCE DISTRIBUTION
    // ========================================================

    renderSafeChart(
        'mgrDistPie',
        '#mgrDistChart',
        {

            series: [

                Number(
                    distribution.outstanding || 0
                ),

                Number(
                    distribution.excellent || 0
                ),

                Number(
                    distribution.very_good || 0
                ),

                Number(
                    distribution.average || 0
                ),

                Number(
                    distribution.needs_improvement || 0
                )

            ],

            chart: {
                type: 'pie',
                height: 220
            },

            labels: [
                'Outstanding (90-100)',
                'Excellent (80-89)',
                'Very Good (70-79)',
                'Average (50-69)',
                'Needs Improvement (<50)'
            ],

            colors: [
                '#D4AF37',
                '#C8102E',
                '#9B0B22',
                '#6B7280',
                '#374151'
            ],

            legend: {
                position: 'bottom',
                fontSize: '10px'
            }
        }
    );


    // ========================================================
    // 3. KRA COMPLETION
    // ========================================================

    const completedKras =
        Number(
            summary.completed_kras || 0
        );

    const pendingKras =
        Number(
            summary.pending_kras || 0
        );


    renderSafeChart(
        'mgrGoalDonut',
        '#mgrGoalDonutChart',
        {

            series: [
                completedKras,
                pendingKras
            ],

            chart: {
                type: 'donut',
                height: 220
            },

            labels: [
                'Completed KRAs',
                'Pending KRAs'
            ],

            colors: [
                '#D4AF37',
                '#E5E7EB'
            ],

            legend: {
                position: 'bottom',
                fontSize: '11px'
            }
        }
    );


    // ========================================================
    // 4. TEAM COMPETENCY RADAR
    // ========================================================

    renderSafeChart(
        'mgrCompetencyRadar',
        '#mgrCompetencyRadarChart',
        {

            series: [
                {
                    name: 'Team Average',

                    data: [

                        Number(
                            competencies.productivity || 0
                        ),

                        Number(
                            competencies.quality_of_work || 0
                        ),

                        Number(
                            competencies.teamwork || 0
                        ),

                        Number(
                            competencies.communication || 0
                        ),

                        Number(
                            competencies.problem_solving || 0
                        ),

                        Number(
                            competencies.initiative || 0
                        )

                    ]
                }
            ],

            chart: {
                type: 'radar',
                height: 260,
                toolbar: {
                    show: false
                }
            },

            colors: ['#C8102E'],

            markers: {
                size: 4,
                colors: ['#D4AF37']
            },

            xaxis: {
                categories: [
                    'Productivity',
                    'Quality of Work',
                    'Teamwork',
                    'Communication',
                    'Problem Solving',
                    'Initiative'
                ]
            },

            yaxis: {
                min: 0,
                max: 100
            }
        }
    );
}
// 3. HR / Admin Dashboard Charts
function initHRApexCharts() {
    renderSafeChart('hrTrendLine', '#hrTrendChart', {
        series: [{ name: "Organization Score", data: [4.1, 4.2, 4.3, 4.4, 4.5, 4.6] }],
        chart: { type: 'line', height: 260, toolbar: { show: false } },
        colors: ['#C8102E'],
        stroke: { curve: 'smooth', width: 2.5 },
        markers: { size: 4, colors: ['#D4AF37'] },
        xaxis: { categories: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'] },
        yaxis: { min: 3.5, max: 5.0 },
        grid: { borderColor: '#E5E7EB', strokeDashArray: 3 }
    });

    renderSafeChart('hrDeptBar', '#hrDeptChart', {
        series: [{ name: "Average Rating Score (%)", data: [82, 89, 91, 84, 80, 86, 88] }],
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: ['#C8102E'],
        plotOptions: { bar: { borderRadius: 5, columnWidth: '40%' } },
        xaxis: { categories: ['HR', 'Loan Proc', 'Credit & Risk', 'Collections', 'CS', 'Finance', 'IT'] },
        yaxis: { min: 70, max: 100 },
        grid: { borderColor: '#E5E7EB', strokeDashArray: 3 }
    });

    renderSafeChart('hrCompDonut', '#hrCompletionChart', {
        series: [510, 40, 10],
        chart: { type: 'donut', height: 230 },
        labels: ['Completed (91%)', 'In Review (7%)', 'Pending Self (2%)'],
        colors: ['#137333', '#D4AF37', '#C8102E'],
        legend: { position: 'bottom', fontSize: '11px' }
    });
}

// --- NOTIFICATIONS ENGINE ---
function renderNotifications() {
    const listEl = document.getElementById('notificationList');
    const badgeEl = document.getElementById('unreadBadge');

    const unreadCount = systemState.notifications.filter(n => n.unread).length;
    if (badgeEl) {
        if (unreadCount > 0) {
            badgeEl.innerText = unreadCount;
            badgeEl.style.display = 'inline-block';
        } else {
            badgeEl.style.display = 'none';
        }
    }

    if (!listEl) return;

    if (systemState.notifications.length === 0) {
        listEl.innerHTML = `<div class="text-center text-muted py-4 fs-7">No notifications found</div>`;
        return;
    }

    listEl.innerHTML = systemState.notifications.map(n => `
        <div class="notification-item ${n.unread ? 'unread' : ''}" onclick="markNotificationRead(${n.id})">
            <div class="notification-icon">
                <i class="bi ${n.type === 'appraisal' ? 'bi-file-earmark-check' : n.type === 'training' ? 'bi-mortarboard' : 'bi-bell'}"></i>
            </div>
            <div style="flex-grow: 1;">
                <div class="notification-title">${n.title}</div>
                <div class="notification-desc">${n.desc}</div>
                <div class="notification-time"><i class="bi bi-clock"></i> ${n.time}</div>
            </div>
            ${n.unread ? '<span class="badge bg-danger rounded-circle p-1" style="width: 7px; height: 7px;"></span>' : ''}
        </div>
    `).join('');
}

async function markNotificationRead(id) {

    try {

        const csrfToken = await getCsrfToken();

        const response = await fetch(
            `/api/notifications/${id}/read`,
            {
                method: 'POST',
                credentials: 'same-origin',

                headers: {
                    'Accept': 'application/json',
                    'X-CSRF-Token': csrfToken
                }
            }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {

            throw new Error(
                data.message ||
                'Failed to mark notification as read.'
            );
        }


        // Update the local notification state

        const notification =
            systemState.notifications.find(
                n => n.id === id
            );


        if (notification) {

            notification.unread = false;
        }


        // Refresh notification display

        renderNotifications();


    } catch (error) {

        console.error(
            'Mark notification read error:',
            error
        );
    }
}

async function markAllNotificationsRead() {
    try {
        const csrfToken = await getCsrfToken();
        const response = await fetch('/api/notifications/read-all', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Accept': 'application/json',
                'X-CSRF-Token': csrfToken
            }
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || 'Failed to update notifications.');
        }

        systemState.notifications.forEach(n => n.unread = false);
        renderNotifications();
    } catch (error) {
        console.error('Mark all notifications read error:', error);
    }
}

function addSampleNotification(title, desc, type = 'system') {
    systemState.notifications.unshift({
        id: Date.now(),
        type: type,
        title: title,
        desc: desc,
        time: 'Just now',
        unread: true
    });
    renderNotifications();
}

// --- REPORT EXPORTS ENGINE (PDF & EXCEL) ---
function generatePDFReport(reportTitle = "Employee Performance Report") {
    const role = systemState.currentRole;
    const user = roleData[role];

    if (window.jspdf && window.jspdf.jsPDF) {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();

        doc.setFillColor(200, 16, 46);
        doc.rect(0, 0, 210, 24, 'F');

        doc.setTextColor(255, 255, 255);
        doc.setFontSize(15);
        doc.setFont('helvetica', 'bold');
        doc.text("MUTHOOT FINANCE - APPRAISAL REPORT", 14, 16);

        doc.setTextColor(31, 41, 55);
        doc.setFontSize(12);
        doc.text(`Report Type: ${reportTitle}`, 14, 34);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.text(`Generated By: ${user.name} (${user.roleTitle})`, 14, 41);
        doc.text(`Branch: ${user.branch} | Department: ${user.department}`, 14, 47);
        doc.text(`Date: ${new Date().toLocaleDateString()}`, 14, 53);

        const headers = [["Employee ID", "Name", "Department", "Score / Rating", "Status"]];
        const data = [
            ["M0018", "Arjun Kumar", "Information Technology", "4.7 ⭐", "In Review"],
            ["M0024", "Meera Jasmine", "Loan Processing", "4.3 ⭐", "Approved"],
            ["M0092", "Vikram Seth", "Credit & Risk", "4.1 ⭐", "Approved"],
            ["M0054", "Reshma Nair", "Customer Service", "4.5 ⭐", "Pending HR"],
            ["M0081", "Siddharth V", "Information Technology", "4.0 ⭐", "Self Submitted"]
        ];

        if (doc.autoTable) {
            doc.autoTable({
                head: headers,
                body: data,
                startY: 59,
                headStyles: { fillColor: [200, 16, 46], textColor: [255, 255, 255] },
                alternateRowStyles: { fillColor: [249, 250, 251] }
            });
        }

        doc.save(`${reportTitle.replace(/\s+/g, '_')}_${Date.now()}.pdf`);
    } else {
        alert(`Generating PDF: ${reportTitle}...\n(Print preview will open)`);
        window.print();
    }

    addSampleNotification('PDF Export Generated', `Downloaded ${reportTitle} in PDF format.`, 'system');
}

function generateExcelReport(reportTitle = "Appraisal_Summary_Report") {
    const data = [
        ["Muthoot Finance - Performance Appraisal Export"],
        ["Generated Date", new Date().toLocaleDateString()],
        [],
        ["Employee ID", "Name", "Department", "Designation", "KPI Score", "Manager Score", "Overall Rating", "Status"],
        ["M0018", "Arjun Kumar", "IT", "Software Executive", "92%", "94%", "4.7 ⭐", "Completed"],
        ["M0024", "Meera Jasmine", "Loan Processing", "Senior Loan Officer", "88%", "86%", "4.3 ⭐", "Approved"],
        ["M0092", "Vikram Seth", "Credit & Risk", "Credit Analyst", "82%", "84%", "4.1 ⭐", "Approved"],
        ["M0054", "Reshma Nair", "Customer Service", "Support Lead", "90%", "90%", "4.5 ⭐", "In Review"],
        ["M0081", "Siddharth V", "IT", "Systems Admin", "80%", "82%", "4.0 ⭐", "Pending"]
    ];

    if (window.XLSX) {
        const ws = XLSX.utils.aoa_to_sheet(data);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Appraisal Report");
        XLSX.writeFile(wb, `${reportTitle}_${Date.now()}.xlsx`);
    } else {
        let csvContent = "data:text/csv;charset=utf-8,";
        data.forEach(row => { csvContent += row.join(",") + "\n"; });
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `${reportTitle}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    addSampleNotification('Excel Export Downloaded', `Exported data for ${reportTitle}.`, 'system');
}

// --- DYNAMIC ROLE SWITCHER & SIDEBAR NAVIGATION CONTROLLER ---
function switchRole(role) {
    systemState.currentRole = role;

    // 1. Update dropdown items
    const items = document.querySelectorAll('.role-dropdown .dropdown-item');
    items.forEach(item => {
        if (item.getAttribute('onclick') && item.getAttribute('onclick').includes(role)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    const labelMap = { employee: 'Role: Employee', manager: 'Role: Manager', hr: 'Role: HR Admin' };
    const textEl = document.getElementById('roleSelectorText');
    if (textEl) textEl.innerText = labelMap[role];

    // 2. Hide all views & show target
    const views = document.querySelectorAll('.dashboard-view');
    views.forEach(v => v.classList.remove('active'));

    const targetView = document.getElementById(`${role}-view`);
    if (targetView) targetView.classList.add('active');

    // 3. Update topbar user details
    const data = roleData[role];
    const nameEl = document.getElementById('welcomeName');
    const roleEl = document.getElementById('welcomeRole');
    const avatarEl = document.getElementById('userAvatar');
    const badgeNameEl = document.getElementById('userBadgeName');
    const badgeRoleEl = document.getElementById('userBadgeRole');

    if (nameEl) nameEl.innerText = data.name;
    if (roleEl) roleEl.innerText = `(${data.roleTitle})`;
    if (avatarEl) avatarEl.src = data.avatar;
    if (badgeNameEl) badgeNameEl.innerText = data.name;
    if (badgeRoleEl) badgeRoleEl.innerText = data.roleTitle;

    // 4. Update Sidebar Menu
    updateSidebarMenu(role);

    // 5. Initialize Role ApexCharts after layout settles
    setTimeout(() => {
        if (role === 'employee') initEmployeeApexCharts();
        else if (role === 'manager') initManagerApexCharts();
        else if (role === 'hr') initHRApexCharts();

        window.dispatchEvent(new Event('resize'));
    }, 100);
}

// --- UPDATE SIDEBAR MENU WITH CONNECTED PAGE LINKS ---
function updateSidebarMenu(role) {
    const menuContainer = document.getElementById('sidebarMenu');
    if (!menuContainer) return;

    // Determine current active page filename / route
    const path = window.location.pathname.toLowerCase();
    const page = path.substring(path.lastIndexOf('/') + 1) || 'index.html';

    let html = '';
    if (role === 'employee') {
        html = `
            <div class="menu-section-header">Main Menu</div>
            <li class="${page.includes('employee') || page.includes('dashboard') || page === 'index.html' ? 'active' : ''}" onclick="window.location.href='/employee-dashboard'"><i class="bi bi-grid-fill"></i> <span>Dashboard</span></li>
            <li class="${page.includes('appraisal') && !page.includes('self') && !page.includes('review') ? 'active' : ''}" onclick="window.location.href='my_appraisals.html'"><i class="bi bi-clipboard-check"></i> <span>My Appraisals</span></li>
            <li class="${page.includes('self') ? 'active' : ''}" onclick="window.location.href='self_appraisal.html'"><i class="bi bi-person-badge"></i> <span>Self-Appraisal</span></li>
            <li class="${page.includes('goals') ? 'active' : ''}" onclick="window.location.href='employee_goals.html'"><i class="bi bi-bullseye"></i> <span>Goals & KRAs</span></li>
            <li class="${page.includes('attendance') && !page.includes('review') ? 'active' : ''}" onclick="window.location.href='employee_attendance.html'"><i class="bi bi-calendar-check"></i> <span>Attendance</span></li>
            <li class="${page.includes('leave') ? 'active' : ''}" onclick="window.location.href='leave_request.html'"><i class="bi bi-calendar-plus"></i> <span>Leave Request</span></li>
            <li class="${page.includes('training') && !page.includes('manage') ? 'active' : ''}" onclick="window.location.href='employee_training.html'"><i class="bi bi-mortarboard"></i> <span>Training</span></li>
        `;
    } else if (role === 'manager') {
        html = `
            <div class="menu-section-header">Manager Overview</div>
            <li class="${page.includes('manager') || page === 'manager_dashboard.html' ? 'active' : ''}" onclick="window.location.href='/manager-dashboard'"><i class="bi bi-grid-fill"></i> <span>Dashboard</span></li>
            <li class="${page.includes('team') ? 'active' : ''}" onclick="window.location.href='/team-evaluation'"><i class="bi bi-people"></i> <span>Team Evaluation</span></li>
            <li class="${page.includes('review') && page.includes('appraisal') ? 'active' : ''}" onclick="window.location.href='/review-appraisal'"><i class="bi bi-clipboard-check"></i> <span>Review Appraisal</span></li>
            <li class="${page.includes('review') && page.includes('attendance') ? 'active' : ''}" onclick="window.location.href='review_attendance.html'"><i class="bi bi-calendar-range"></i> <span>Review Attendance</span></li>
            <li class="${page.includes('behaviour') ? 'active' : ''}" onclick="window.location.href='behaviour_rating.html'"><i class="bi bi-star-half"></i> <span>Behaviour Rating</span></li>
            <li class="${page.includes('feedback') || page.includes('360') ? 'active' : ''}" onclick="window.location.href='feedback_360.html'"><i class="bi bi-chat-square-text"></i> <span>360 Feedback</span></li>
            <li class="${page.includes('assign') && page.includes('kra') ? 'active' : ''}" onclick="window.location.href='assign_kra.html'"><i class="bi bi-ui-checks"></i> <span>Assign KRAs</span></li>
            <li class="${page.includes('kpi_records') || page.includes('kpi-records') ? 'active' : ''}" onclick="window.location.href='kpi_records.html'"><i class="bi bi-speedometer2"></i> <span>KPI Records</span></li>
        `;
    } else if (role === 'hr') {
        html = `
            <div class="menu-section-header">HR Administration</div>
            <li class="${page.includes('hr_dashboard') || page.includes('hr-dashboard') ? 'active' : ''}" onclick="window.location.href='hr_dashboard.html'"><i class="bi bi-grid-fill"></i> <span>Dashboard</span></li>
            <li class="${page.includes('performance') ? 'active' : ''}" onclick="window.location.href='performance_results.html'"><i class="bi bi-award"></i> <span>Performance Results</span></li>
            <li class="${page.includes('manage_training') || page.includes('manage-training') || page.includes('training_details') ? 'active' : ''}" onclick="window.location.href='manage_training.html'"><i class="bi bi-mortarboard-fill"></i> <span>Manage Training</span></li>
            <li class="${page.includes('kra_management') || page.includes('kra-management') ? 'active' : ''}" onclick="window.location.href='kra_management.html'"><i class="bi bi-bullseye"></i> <span>KRA Management</span></li>
            <li class="${page.includes('kpi_management') || page.includes('kpi-management') ? 'active' : ''}" onclick="window.location.href='kpi_management.html'"><i class="bi bi-speedometer2"></i> <span>KPI Management</span></li>
            <li class="${page.includes('assign_kra') || page.includes('assign-kra') ? 'active' : ''}" onclick="window.location.href='assign_kra.html'"><i class="bi bi-person-check"></i> <span>Assign KRA</span></li>
            <li class="${page.includes('assign_kpi') || page.includes('assign-kpi') ? 'active' : ''}" onclick="window.location.href='assign_kpi.html'"><i class="bi bi-person-lines-fill"></i> <span>Assign KPI</span></li>
            <li class="${page.includes('report') ? 'active' : ''}" onclick="window.location.href='kra_kpi_report.html'"><i class="bi bi-file-earmark-bar-graph"></i> <span>KRA / KPI Report</span></li>
        `;
    }

    html += `
        <div class="menu-section-header">Account</div>
        <li class="${page.includes('profile') ? 'active' : ''}" onclick="window.location.href='profile.html'"><i class="bi bi-person-circle"></i> <span>My Profile</span></li>
        <li onclick="window.location.href='login.html'"><i class="bi bi-box-arrow-right"></i> <span>Sign Out</span></li>
    `;

    menuContainer.innerHTML = html;
}

// ============================================================
// PAGE INITIALIZATION
// ============================================================

window.addEventListener(
    'DOMContentLoaded',
    () => {

        const activeView =
            document.querySelector(
                '.dashboard-view.active'
            );


        if (activeView) {

            const viewId =
                activeView.id.replace(
                    '-view',
                    ''
                );


            switchRole(viewId);

        } else {

            const path =
                window.location.pathname.toLowerCase();


            if (
                path.includes('manager') ||
                path.includes('team') ||
                path.includes('team_evaluation') ||
                path.includes('team-evaluation') ||
                path.includes('review') ||
                path.includes('behaviour') ||
                path.includes('feedback') ||
                path.includes('kpi_records') ||
                path.includes('kpi-records')
            ) {

                updateSidebarMenu('manager');

            } else if (
                path.includes('hr') ||
                path.includes('kra') ||
                path.includes('kpi') ||
                path.includes('assign') ||
                path.includes('manage_training') ||
                path.includes('manage-training')
            ) {

                updateSidebarMenu('hr');

            } else {

                updateSidebarMenu('employee');
            }
        }


        // ================================================
        // EMPLOYEE DASHBOARD
        // ================================================

        if (
            document.getElementById(
                'employee-view'
            )
        ) {

            loadEmployeeDashboardData();
        }
        // ================================================
        // MANAGER DASHBOARD
        // ================================================

        if (
            document.getElementById(
                'manager-view'
            )
        ) {

            loadManagerDashboardData();

        }

        // Initialize Muthoot Interactive Button Animations
        initInteractiveButtons();

    }
);

// --- MUTHOOT INTERACTIVE BUTTON ANIMATION ENGINE ---
function initInteractiveButtons() {
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-muthoot, .btn-muthoot-outline, .btn-muthoot-interactive, [data-interactive="true"]');
        if (!btn || btn.disabled || btn.classList.contains('btn-animating')) return;

        // Skip dropdown toggles
        if (btn.hasAttribute('data-bs-toggle') && btn.getAttribute('data-bs-toggle') === 'dropdown') return;

        // Create Gold/Red Ripple
        const rect = btn.getBoundingClientRect();
        const ripple = document.createElement('span');
        const diameter = Math.max(rect.width, rect.height);
        const radius = diameter / 2;

        ripple.style.width = ripple.style.height = `${diameter}px`;
        ripple.style.left = `${e.clientX - rect.left - radius}px`;
        ripple.style.top = `${e.clientY - rect.top - radius}px`;
        ripple.classList.add('btn-ripple');

        const existingRipple = btn.querySelector('.btn-ripple');
        if (existingRipple) existingRipple.remove();
        btn.appendChild(ripple);

        // Interactive Success Feedback for Submit & Action buttons
        if (btn.type === 'submit' || btn.getAttribute('data-action') === 'submit' || btn.classList.contains('btn-submit-anim') || btn.classList.contains('btn-muthoot-interactive')) {
            btn.classList.add('btn-animating');
            const originalHTML = btn.innerHTML;

            setTimeout(() => {
                btn.classList.add('btn-success-animated');
                btn.innerHTML = `<i class="bi bi-check-circle-fill me-1 btn-success-icon"></i> Done!`;
            }, 180);

            setTimeout(() => {
                btn.innerHTML = originalHTML;
                btn.classList.remove('btn-success-animated', 'btn-animating');
            }, 1800);
        }
    });
}
