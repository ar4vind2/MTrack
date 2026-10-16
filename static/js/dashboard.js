/* ==========================================================================
   MUTHOOT FINANCE EMPLOYEE APPRAISAL SYSTEM - DASHBOARD CONTROLLER (MEMBER 6)
   ApexCharts Integration, PDF/Excel Report Exports, Notifications Engine
   ========================================================================== */

// --- GLOBAL STATE ---
const systemState = {
    currentRole: 'employee',
    notifications: []
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

// Default role metadata
const roleData = {
    employee: {
        name: "Employee",
        roleTitle: "Employee",
        department: "Information Technology",
        branch: "Main Branch",
        avatar: "",
        stats: { overallScore: "—", attendance: "—", goalsCompleted: "—", trainingStatus: "—" }
    },
    manager: {
        name: "Manager",
        roleTitle: "Branch Manager",
        department: "Operations",
        branch: "Main Branch",
        avatar: "",
        stats: { teamAverage: "—", pendingReviews: "0", completedReviews: "0", totalEmployees: "0" }
    },
    hr: {
        name: "HR Admin",
        roleTitle: "Human Resources",
        department: "Human Resources",
        branch: "Head Office",
        avatar: "",
        stats: { totalEmployees: "0", avgRating: "—", completedAppraisals: "0", pendingReviews: "0" }
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

function switchEmpTrendType(type = 'monthly', btnEl = null) {
    if (!window.empPerformanceTrends) return;

    // Update active button state
    const btnGroup = document.getElementById('empTrendFilterGroup');
    if (btnGroup) {
        btnGroup.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    }
    if (btnEl) {
        btnEl.classList.add('active');
    } else {
        const targetBtn = document.getElementById(`btnTrend${type.charAt(0).toUpperCase() + type.slice(1)}`);
        if (targetBtn) targetBtn.classList.add('active');
    }

    const titleEl = document.getElementById('empTrendTitle');
    const subtitleEl = document.getElementById('empTrendSubtitle');
    const titleMap = {
        monthly: 'Monthly Performance Trend',
        quarterly: 'Quarterly Performance Trend',
        annual: 'Annual Performance Trend',
        all: 'All Performance Cycles Trend'
    };
    const subMap = {
        monthly: 'Progression of monthly appraisal assessment ratings',
        quarterly: 'Progression of quarterly appraisal ratings',
        annual: 'Progression of annual appraisal cycle ratings',
        all: 'Comprehensive progression across all appraisal cycles'
    };

    if (titleEl) titleEl.innerHTML = `<i class="bi bi-graph-up"></i> ${titleMap[type] || 'Performance Trend'}`;
    if (subtitleEl) subtitleEl.textContent = subMap[type] || 'Progression of periodic assessment ratings';

    const trendData = window.empPerformanceTrends[type] || [];
    renderSafeChart('empTrend', '#empTrendChart', {
        series: [
            {
                name: "Performance Score",
                data: trendData.map(item => Number(item.score || 0))
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
            categories: trendData.map(item => String(item.label || item.year))
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
}

function initEmployeeApexCharts(data = employeeDashboardData) {

    if (!data) {
        console.warn("Employee dashboard data is not available yet.");
        return;
    }

    const performance = data.performance || {};
    const attendance = data.attendance || {};
    const kra = data.kra || {};

    window.empPerformanceTrends = data.performance_trends || {
        monthly: data.performance_trend || [],
        quarterly: [],
        annual: [],
        all: data.performance_trend || []
    };
    window.currentCycleId = data.cycle_id || (data.performance && data.performance.cycle_id);

    // Initial render of employee trend (defaults to monthly if present, else all)
    const initialType = (window.empPerformanceTrends.monthly && window.empPerformanceTrends.monthly.length > 0) ? 'monthly' : 'all';
    switchEmpTrendType(initialType);


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

        labels: [
            'KRA Goals'
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

    // ========================================================
    // 4. PERFORMANCE RADAR CHART
    // ========================================================

    const kpiScore =
        Number(performance.kpi_score || 0);

    const managerScore =
        Number(performance.manager_score || 0);

    const attendanceScore =
        Number(performance.attendance_score || 0);

    const behaviourScore =
        Number(performance.behaviour_score || 0);

    const selfAppraisalScore =
        Number(performance.self_appraisal_score || 0);

    const trainingScore =
        Number(performance.training_score || 0);


    renderSafeChart(
        'empPerformanceRadar',
        '#empPerformanceRadarChart',
        {

            series: [
                {
                    name: 'Performance Score',

                    data: [
                        kpiScore,
                        managerScore,
                        attendanceScore,
                        behaviourScore,
                        selfAppraisalScore,
                        trainingScore
                    ]
                }
            ],

            chart: {
                type: 'radar',
                height: 300,
                toolbar: {
                    show: false
                }
            },

            xaxis: {
                categories: [
                    'KPI',
                    'Manager',
                    'Attendance',
                    'Behaviour',
                    'Self-Appraisal',
                    'Training'
                ]
            },

            yaxis: {
                min: 0,
                max: 100,
                tickAmount: 5
            },

            stroke: {
                width: 2
            },

            markers: {
                size: 4
            },

            dataLabels: {
                enabled: true,

                formatter: function(value) {
                    return Number(value).toFixed(0);
                }
            },

            tooltip: {
                y: {
                    formatter: function(value) {
                        return Number(value).toFixed(2) + '%';
                    }
                }
            },

            fill: {
                opacity: 0.2
            }

        }
    );
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
    const isMgrPage = window.location.pathname.includes('manager-dashboard') || window.location.pathname.includes('manager_dashboard') || window.location.pathname === '/';
    if (!isMgrPage) {
        return;
    }

    const table = document.querySelector('#manager-view .table-muthoot');
    if (!table || !table.textContent.includes('Self Rating')) {
        return;
    }

    const tbody = table.querySelector('tbody');
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

    // Update performance breakdown
    updateEmployeePerformanceSummary(data);
}
// ============================================================
// EMPLOYEE APPRAISAL SUMMARY
// ============================================================

// ============================================================
// EMPLOYEE APPRAISAL SUMMARY
// ============================================================

function updateEmployeeAppraisalSummary(data) {

    const summaryCard =
        document.getElementById(
            'employeeAppraisalTable'
        );

    if (!summaryCard) {
        return;
    }

    const performance =
        data.performance || {};

    const year =
        performance.year || '—';

    const score =
        performance.final_score !== null &&
        performance.final_score !== undefined

            ? Number(
                performance.final_score
              ).toFixed(2) + '%'

            : '—';

    const rating =
        performance.rating ||
        'Not Available';

    const recommendation =
        performance.recommendation ||
        'Not Available';


    // --------------------------------------------------------
    // Appraisal Year
    // --------------------------------------------------------

    const yearElement =
        document.getElementById(
            'appraisalYear'
        );

    if (yearElement) {
        yearElement.textContent = year;
    }


    // --------------------------------------------------------
    // Final Score
    // --------------------------------------------------------

    const scoreElement =
        document.getElementById(
            'appraisalScore'
        );

    if (scoreElement) {
        scoreElement.textContent = score;
    }


    // --------------------------------------------------------
    // Reviewer
    // --------------------------------------------------------

    const reviewerElement =
        document.getElementById(
            'appraisalReviewer'
        );

    if (reviewerElement) {
        reviewerElement.textContent =
            'System Calculated';
    }


    // --------------------------------------------------------
    // Rating
    // --------------------------------------------------------

    const ratingElement =
        document.getElementById(
            'appraisalRating'
        );

    if (ratingElement) {
        ratingElement.textContent =
            rating;
    }


    // --------------------------------------------------------
    // Recommendation
    // --------------------------------------------------------

    const recommendationElement =
        document.getElementById(
            'appraisalRecommendation'
        );

    if (recommendationElement) {
        recommendationElement.textContent =
            recommendation;
    }
}

// ============================================================
// EMPLOYEE PERFORMANCE SCORE BREAKDOWN
// ============================================================

function updateEmployeePerformanceSummary(data) {

    const performance =
        data.performance || {};

    // --------------------------------------------------------
    // Helper for displaying percentages
    // --------------------------------------------------------

    function formatScore(value) {

        if (
            value === null ||
            value === undefined
        ) {
            return '—';
        }

        return Number(value).toFixed(2) + '%';
    }


    // --------------------------------------------------------
    // Final Score
    // --------------------------------------------------------

    const finalScore =
        document.getElementById(
            'employeeFinalScore'
        );

    if (finalScore) {

        finalScore.textContent =
            formatScore(
                performance.final_score
            );
    }


    // --------------------------------------------------------
    // Rating
    // --------------------------------------------------------

    const rating =
        document.getElementById(
            'employeeRating'
        );

    if (rating) {

        rating.textContent =
            performance.rating ||
            'Not Available';
    }


    // --------------------------------------------------------
    // Recommendation
    // --------------------------------------------------------

    const recommendation =
        document.getElementById(
            'employeeRecommendation'
        );

    if (recommendation) {

        recommendation.textContent =
            performance.recommendation ||
            'Not Available';
    }


    // --------------------------------------------------------
    // KPI Score
    // --------------------------------------------------------

    const kpiScore =
        document.getElementById(
            'employeeKpiScore'
        );

    if (kpiScore) {

        kpiScore.textContent =
            formatScore(
                performance.kpi_score
            );
    }


    // --------------------------------------------------------
    // Manager Score
    // --------------------------------------------------------

    const managerScore =
        document.getElementById(
            'employeeManagerScore'
        );

    if (managerScore) {

        managerScore.textContent =
            formatScore(
                performance.manager_score
            );
    }


    // --------------------------------------------------------
    // Attendance Score
    // --------------------------------------------------------

    const attendanceScore =
        document.getElementById(
            'employeeAttendanceScore'
        );

    if (attendanceScore) {

        attendanceScore.textContent =
            formatScore(
                performance.attendance_score
            );
    }


    // --------------------------------------------------------
    // Behaviour Score
    // --------------------------------------------------------

    const behaviourScore =
        document.getElementById(
            'employeeBehaviourScore'
        );

    if (behaviourScore) {

        behaviourScore.textContent =
            formatScore(
                performance.behaviour_score
            );
    }


    // --------------------------------------------------------
    // Self-Appraisal Score
    // --------------------------------------------------------

    const selfAppraisalScore =
        document.getElementById(
            'employeeSelfAppraisalScore'
        );

    if (selfAppraisalScore) {

        selfAppraisalScore.textContent =
            formatScore(
                performance.self_appraisal_score
            );
    }


    // --------------------------------------------------------
    // Training Score
    // --------------------------------------------------------

    const trainingScore =
        document.getElementById(
            'employeeTrainingScore'
        );

    if (trainingScore) {

        trainingScore.textContent =
            formatScore(
                performance.training_score
            );
    }
}

// ============================================================
// NOTIFICATIONS FROM FLASK
// ============================================================

function renderNotificationsFromAPI(notifications) {
    if (!Array.isArray(notifications)) return;

    const seen = new Set();
    const uniqueList = [];

    for (const notification of notifications) {
        const title = (notification.title || 'Notification').trim();
        const desc = (notification.message || notification.desc || '').trim();
        const key = `${title}:::${desc}`;

        if (!seen.has(key)) {
            seen.add(key);
            uniqueList.push({
                id: notification.id,
                type: notification.type || 'system',
                title: title,
                desc: desc,
                time: formatNotificationTime(notification.created_at),
                unread: !notification.is_read
            });
        }
    }

    systemState.notifications = uniqueList;
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
                Number(distribution.outstanding || 0),
                Number(distribution.excellent || 0),
                Number(distribution.good !== undefined ? distribution.good : (distribution.very_good || 0)),
                Number(distribution.needs_improvement || 0),
                Number(distribution.unsatisfactory || 0)
            ],
            chart: {
                type: 'pie',
                height: 220
            },
            labels: [
                'Outstanding (≥90%)',
                'Excellent (80-89%)',
                'Good (70-79%)',
                'Needs Improvement (60-69%)',
                'Unsatisfactory (<60%)'
            ],
            colors: [
                '#D4AF37',
                '#0d6efd',
                '#198754',
                '#ffc107',
                '#dc3545'
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
// 3. HR / Admin Dashboard Charts (Live Database Data)
async function initHRApexCharts() {
    let hrData = null;
    try {
        const response = await fetch('/api/hr/dashboard-data', { credentials: 'same-origin' });
        if (response.ok) {
            hrData = await response.json();
        }
    } catch (e) {
        console.error("Failed to load HR dashboard data:", e);
    }

    // Default fallbacks if network or server error
    const totalEmployees = hrData?.stats?.total_employees ?? 0;
    const avgRatingDisplay = hrData?.stats?.avg_rating_display ?? "—";
    const completedDisplay = hrData?.stats?.completed_display ?? "0 (0%)";
    const pendingReviews = hrData?.stats?.pending_reviews ?? 0;

    const elTotal = document.getElementById('hrTotalEmployees');
    if (elTotal) elTotal.innerText = `${totalEmployees} Staff`;

    const elAvg = document.getElementById('hrAvgRating');
    if (elAvg) elAvg.innerText = avgRatingDisplay;

    const elComp = document.getElementById('hrCompletedAppraisals');
    if (elComp) elComp.innerText = completedDisplay;

    const elPending = document.getElementById('hrPendingReviews');
    if (elPending) elPending.innerText = `${pendingReviews} Reviews`;

    // 1. Monthly Trend Line Chart
    const trendCats = hrData?.monthly_trend?.categories ?? ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'];
    const trendSeries = hrData?.monthly_trend?.series ?? [3.8, 4.0, 4.1, 4.2, 4.3, 4.4];
    renderSafeChart('hrTrendLine', '#hrTrendChart', {
        series: [{ name: "Organization Score", data: trendSeries }],
        chart: { type: 'line', height: 260, toolbar: { show: false } },
        colors: ['#DD3026'],
        stroke: { curve: 'smooth', width: 3 },
        markers: { size: 5, colors: ['#FFFFFF'], strokeColors: '#DD3026', strokeWidth: 2 },
        xaxis: { categories: trendCats },
        yaxis: { min: 0, max: 5.0 },
        grid: { borderColor: '#E2E8F0', strokeDashArray: 3 }
    });

    // 2. Department Comparison Bar Chart
    const deptCats = hrData?.department_performance?.categories ?? ['HR', 'Finance', 'IT', 'Operations'];
    const deptScores = hrData?.department_performance?.series ?? [85, 78, 92, 88];
    renderSafeChart('hrDeptBar', '#hrDeptChart', {
        series: [{ name: "Average Rating Score (%)", data: deptScores }],
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: ['#DD3026'],
        plotOptions: { bar: { borderRadius: 6, columnWidth: '42%' } },
        xaxis: { categories: deptCats },
        yaxis: { min: 0, max: 100 },
        grid: { borderColor: '#E2E8F0', strokeDashArray: 3 }
    });

    // 3. Completion Donut Chart
    const completed = hrData?.completion?.completed ?? 0;
    const inReview = hrData?.completion?.in_review ?? 0;
    const pendingSelf = hrData?.completion?.pending_self ?? 0;
    const totalComp = completed + inReview + pendingSelf || 1;
    const compPct = Math.round((completed / totalComp) * 100);
    const revPct = Math.round((inReview / totalComp) * 100);
    const pendPct = Math.round((pendingSelf / totalComp) * 100);

    renderSafeChart('hrCompDonut', '#hrCompletionChart', {
        series: [completed, inReview, pendingSelf],
        chart: { type: 'donut', height: 230 },
        labels: [`Completed (${compPct}%)`, `In Review (${revPct}%)`, `Pending Self (${pendPct}%)`],
        colors: ['#00855B', '#565E74', '#DD3026'],
        legend: { position: 'bottom', fontSize: '11px', fontFamily: 'Inter' }
    });

    // 4. Recommendations Table
    const tbody = document.getElementById('hrRecommendationsTableBody');
    if (tbody && hrData?.recommendations) {
        if (hrData.recommendations.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No recommendations found.</td></tr>`;
        } else {
            tbody.innerHTML = hrData.recommendations.map(r => {
                const isNeedsImprovement = (r.rating && r.rating.toLowerCase().includes('needs improvement')) ||
                                          (r.recommendation && r.recommendation.toLowerCase().includes('training')) ||
                                          (r.final_score < 70);

                const ratingBadgeClass = r.final_score >= 80 ? 'bg-success' : (r.final_score >= 60 ? 'bg-primary' : 'bg-warning text-dark');
                const recBadgeClass = isNeedsImprovement ? 'bg-warning-subtle text-warning-emphasis border border-warning' : 'bg-danger-subtle text-danger border border-danger-subtle';

                let actionsHtml = '';
                if (isNeedsImprovement) {
                    actionsHtml = `
                        <a href="/manage-training" class="btn btn-sm btn-muthoot-outline" title="Assign Recommended Training">
                            <i class="bi bi-mortarboard me-1"></i>Assign Training
                        </a>
                    `;
                } else {
                    actionsHtml = `
                        <div class="btn-group btn-group-sm">
                            ${r.is_promoted
                                ? '<span class="badge bg-light text-success border border-success"><i class="bi bi-check-circle me-1"></i>Promoted</span>'
                                : `<button class="btn btn-sm btn-muthoot" onclick="approvePromotion(${r.employee_id}, '${r.employee_name}')"><i class="bi bi-award me-1"></i>Promote</button>`}
                            ${r.is_incremented
                                ? '<span class="badge bg-light text-primary border border-primary ms-1"><i class="bi bi-check-circle me-1"></i>Incremented</span>'
                                : `<button class="btn btn-sm btn-muthoot-outline ms-1" onclick="approveIncrement(${r.employee_id}, '${r.employee_name}')"><i class="bi bi-graph-up-arrow me-1"></i>Increment</button>`}
                        </div>
                    `;
                }

                return `
                    <tr>
                        <td><strong>${r.employee_code}</strong></td>
                        <td>${r.employee_name}</td>
                        <td>${r.department}</td>
                        <td><span class="badge ${ratingBadgeClass}">${r.rating} (${r.final_score}%)</span></td>
                        <td><span class="${isNeedsImprovement ? 'text-muted' : 'text-primary fw-semibold'}">${r.suggested_increment}</span></td>
                        <td><span class="badge ${recBadgeClass}">${r.recommendation}</span></td>
                        <td class="text-end">
                            ${actionsHtml}
                        </td>
                    </tr>
                `;
            }).join('');
        }
    }
}

async function approvePromotion(employeeId, employeeName) {
    if (!confirm(`Are you sure you want to approve the promotion for ${employeeName}?`)) return;
    try {
        const csrfToken = await getCsrfToken();
        const res = await fetch('/api/hr/approve-promotion', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
            body: JSON.stringify({ employee_id: employeeId })
        });
        const json = await res.json();
        if (json.success) {
            alert(json.message);
            initHRApexCharts();
        } else {
            alert(json.message || "Failed to approve promotion.");
        }
    } catch (e) {
        alert("Error approving promotion: " + e.message);
    }
}

async function approveIncrement(employeeId, employeeName) {
    const amount = prompt(`Enter annual increment amount for ${employeeName} (INR):`, "5000");
    if (!amount) return;
    try {
        const csrfToken = await getCsrfToken();
        const res = await fetch('/api/hr/approve-increment', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
            body: JSON.stringify({ employee_id: employeeId, increment_amount: parseFloat(amount) })
        });
        const json = await res.json();
        if (json.success) {
            alert(json.message);
            initHRApexCharts();
        } else {
            alert(json.message || "Failed to approve increment.");
        }
    } catch (e) {
        alert("Error approving increment: " + e.message);
    }
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
            badgeEl.classList.remove('d-none');
        } else {
            badgeEl.innerText = '0';
            badgeEl.style.display = 'none';
        }
    }

    if (!listEl) return;

    if (systemState.notifications.length === 0) {
        listEl.innerHTML = `<div class="text-center text-muted py-4 fs-7">No notifications found</div>`;
        return;
    }

    const hasUnread = systemState.notifications.some(n => n.unread);
    const headerHtml = `
        <div class="d-flex justify-content-between align-items-center mb-2 px-1">
            <span class="text-muted fs-7 fw-semibold">Recent Alerts</span>
            ${hasUnread ? '<button class="btn btn-link btn-sm p-0 text-danger text-decoration-none fs-7 fw-semibold" onclick="markAllNotificationsRead()">Mark all read</button>' : ''}
        </div>
    `;

    const itemsHtml = systemState.notifications.map(n => {
        const type = (n.type || '').toLowerCase();
        let iconClass = 'bi-bell';
        if (type.includes('appraisal')) iconClass = 'bi-file-earmark-check';
        else if (type.includes('training')) iconClass = 'bi-mortarboard';
        else if (type.includes('leave')) iconClass = 'bi-calendar-check';
        else if (type.includes('promotion') || type.includes('increment') || type.includes('award')) iconClass = 'bi-award';
        else if (type.includes('goal') || type.includes('kra') || type.includes('kpi')) iconClass = 'bi-bullseye';

        return `
        <div class="notification-item ${n.unread ? 'unread' : ''}" onclick="markNotificationRead(${n.id})">
            <div class="notification-icon">
                <i class="bi ${iconClass}"></i>
            </div>
            <div style="flex-grow: 1;">
                <div class="notification-title">${n.title}</div>
                <div class="notification-desc">${n.desc}</div>
                <div class="notification-time"><i class="bi bi-clock"></i> ${n.time}</div>
            </div>
            ${n.unread ? '<span class="badge bg-danger rounded-circle p-1" style="width: 7px; height: 7px;"></span>' : ''}
        </div>
        `;
    }).join('');

    listEl.innerHTML = headerHtml + itemsHtml;
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

// --- HELPER: EXTRACT ACTIVE TABLE DATA FOR EXPORT ---
function getActiveTableData() {
    const table = document.querySelector('.table-muthoot') || document.querySelector('table');
    if (!table) return { headers: [], rows: [] };

    const thEls = Array.from(table.querySelectorAll('thead th'));
    const headers = thEls.map(th => th.innerText.trim()).filter(h => h && !['action', 'actions'].includes(h.toLowerCase()));

    const rowEls = Array.from(table.querySelectorAll('tbody tr'));
    const rows = [];
    for (const tr of rowEls) {
        const text = tr.innerText.trim();
        if (text.toLowerCase().includes('no records') ||
            text.toLowerCase().includes('no appraisal') ||
            text.toLowerCase().includes('no training') ||
            text.toLowerCase().includes('no recommendations') ||
            text.toLowerCase().includes('no employees') ||
            text.toLowerCase().includes('loading')) {
            continue;
        }
        const tdEls = Array.from(tr.querySelectorAll('td'));
        if (tdEls.length === 0) continue;
        const rowData = tdEls.slice(0, headers.length).map(td => td.innerText.trim().replace(/\s+/g, ' '));
        rows.push(rowData);
    }
    return { headers, rows };
}

// --- REPORT EXPORTS ENGINE (REPORTLAB PDF & OPENPYXL EXCEL VIA SERVER) ---
function generatePDFReport(reportTitle = "Employee Performance Report") {
    const encodedTitle = encodeURIComponent(reportTitle);
    const cycleQuery = window.currentCycleId ? `&cycle_id=${window.currentCycleId}` : '';
    window.location.href = `/api/reports/generate-pdf?title=${encodedTitle}${cycleQuery}`;
    if (typeof addSampleNotification === 'function') {
        addSampleNotification('PDF Export Generated', `Downloaded ${reportTitle} in ReportLab PDF format.`, 'system');
    }
}

function generateExcelReport(reportTitle = "Appraisal_Summary_Report") {
    const encodedTitle = encodeURIComponent(reportTitle);
    const cycleQuery = window.currentCycleId ? `&cycle_id=${window.currentCycleId}` : '';
    window.location.href = `/api/reports/generate-excel?title=${encodedTitle}${cycleQuery}`;
    if (typeof addSampleNotification === 'function') {
        addSampleNotification('Excel Export Downloaded', `Exported data for ${reportTitle} in OpenPyXL Excel format.`, 'system');
    }
}

// --- DETECT LOGGED IN USER ROLE ACCURATELY ---
function detectUserRole() {
    // 1. Check meta tag (highest priority, set by server template)
    const metaEl = document.querySelector('meta[name="user-role"]');
    if (metaEl && metaEl.content) {
        const metaRole = metaEl.content.toLowerCase().trim();
        if (metaRole.includes('hr') || metaRole.includes('admin') || metaRole.includes('human')) return 'hr';
        if (metaRole.includes('manager')) return 'manager';
        if (metaRole.includes('employee')) return 'employee';
    }

    // 2. Explicit Pathname detection
    const path = window.location.pathname.toLowerCase();
    const employeePaths = [
        'employee-dashboard', 'employee_dashboard',
        'appraisal-form', 'appraisal_form',
        'self-appraisal', 'self_appraisal',
        'leave-request', 'leave_request',
        'requested-leaves', 'requested_leaves',
        'employee-training', 'employee_training',
        'employee-goals', 'employee_goals',
        'employee-attendance', 'employee_attendance',
        'my-appraisals', 'my_appraisals'
    ];
    if (employeePaths.some(p => path.includes(p))) {
        return 'employee';
    }

    const managerPaths = [
        'manager-dashboard', 'manager_dashboard',
        'team-evaluation', 'team_evaluation',
        'review-appraisal', 'review_appraisal',
        'review-employee-appraisal',
        'manager/appraisal', 'manager-appraisal', 'manager_appraisal',
        'review-attendance', 'review_attendance',
        'behaviour-rating', 'behaviour_rating',
        'approve-leaves', 'approve_leaves'
    ];
    if (managerPaths.some(p => path.includes(p))) {
        return 'manager';
    }

    const hrPaths = [
        'hr-dashboard', 'hr_dashboard',
        'admin-dashboard', 'admin_dashboard',
        'performance-results', 'performance_results',
        'employee-performance',
        'manage-training', 'manage_training',
        'training-details', 'training_details',
        'kra-management', 'kra_management',
        'kpi-management', 'kpi_management',
        'assign-kra', 'assign-kpi',
        'kpi-records', 'appraisal-cycles', 'kra-kpi-report',
        'admin/employees', 'admin/hierarchy', 'admin/departments',
        'admin/branches', 'admin/designations', 'admin/users',
        'employee_management', 'employee-management',
        'employee_hierarchy', 'employee-hierarchy',
        'department_management', 'branch_management',
        'designation_management', 'user_management',
        'add_employee', 'edit_employee', 'employee_profile'
    ];
    if (hrPaths.some(p => path.includes(p))) {
        return 'hr';
    }

    // 3. Check welcome / badge role text (rendered by Flask {{ session.get('role_name') }})
    const roleEl = document.getElementById('welcomeRole') || document.getElementById('userBadgeRole');
    if (roleEl) {
        const text = roleEl.textContent.trim().toLowerCase();
        if (text === 'human resources' || text === 'hr' || text.startsWith('hr ') || text === 'admin') return 'hr';
        if (text === 'manager') return 'manager';
        if (text === 'employee') return 'employee';
    }

    return 'employee';
}

// --- DYNAMIC ROLE SWITCHER & SIDEBAR NAVIGATION CONTROLLER ---
function switchRole(role) {
    if (!roleData[role]) return;
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

    // 3. Update topbar user details ONLY if on multi-view prototype index.html
    const isMultiViewDemo = document.querySelectorAll('.dashboard-view').length > 1;
    if (isMultiViewDemo) {
        const data = roleData[role];
        const nameEl = document.getElementById('welcomeName');
        const roleEl = document.getElementById('welcomeRole');
        const avatarEl = document.getElementById('userAvatar');
        const badgeNameEl = document.getElementById('userBadgeName');
        const badgeRoleEl = document.getElementById('userBadgeRole');

        if (nameEl) nameEl.innerText = data.name;
        if (roleEl) roleEl.innerText = data.roleTitle;
        if (avatarEl) {
            if (data.avatar) {
                avatarEl.src = data.avatar;
            } else {
                avatarEl.style.display = 'none';
            }
        }
        if (badgeNameEl) badgeNameEl.innerText = data.name;
        if (badgeRoleEl) badgeRoleEl.innerText = data.roleTitle;
    }

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

// --- NORMALIZE ROLE HELPER ---
function normalizeRole(role) {
    if (!role) return 'employee';
    const r = role.toString().trim().toLowerCase();
    if (r.includes('hr') || r.includes('admin') || r.includes('human')) return 'hr';
    if (r.includes('manager') || r.includes('lead') || r.includes('supervisor')) return 'manager';
    return 'employee';
}

// --- GLOBAL GO BACK DASHBOARD HELPER ---
function goBackDashboard() {
    const metaRole = (document.querySelector('meta[name="user-role"]')?.content || '').toLowerCase();
    const role = normalizeRole(metaRole);
    if (window.history.length > 1 && document.referrer && document.referrer.includes(window.location.host) && !document.referrer.includes('login') && !document.referrer.includes('profile')) {
        window.history.back();
    } else {
        if (role === 'hr') {
            window.location.href = '/hr-dashboard';
        } else if (role === 'manager') {
            window.location.href = '/manager-dashboard';
        } else {
            window.location.href = '/employee-dashboard';
        }
    }
}

// --- UPDATE SIDEBAR MENU WITH CONNECTED PAGE LINKS ---
function updateSidebarMenu(role) {
    const menuContainer = document.getElementById('sidebarMenu');
    if (!menuContainer) return;

    role = normalizeRole(role);

    // Determine current active page filename / route
    const rawPath = window.location.pathname.toLowerCase().replace(/\/+$/, '') || '/';
    const page = rawPath.substring(rawPath.lastIndexOf('/') + 1);

    let html = '';
    if (role === 'employee') {
        const isDash = page === 'employee-dashboard' || page === 'employee_dashboard.html' || (rawPath === '/' && role === 'employee');
        const isAppraisal = page === 'my-appraisals' || page === 'my_appraisals.html' || (page.includes('appraisal') && !page.includes('self') && !page.includes('review') && !page.includes('cycle'));
        const isSelf = page === 'self-appraisal' || page === 'self_appraisal.html' || page === 'appraisal-form' || page === 'appraisal_form.html';
        const isGoals = page === 'employee-goals' || page === 'employee_goals.html' || (page.includes('goals') && !page.includes('dashboard'));
        const isAttend = page === 'employee-attendance' || page === 'employee_attendance.html';
        const isLeave = page === 'leave-request' || page === 'leave_request.html';
        const isMyLeaves = page === 'requested-leaves' || page === 'requested_leaves.html';
        const isTrain = page === 'employee-training' || page === 'employee_training.html';

        html = `
            <div class="menu-section-header">Main Menu</div>
            <li class="${isDash ? 'active' : ''}" onclick="window.location.href='/employee-dashboard'"><i class="bi bi-grid-fill"></i> <span>Dashboard</span></li>
            <li class="${isAppraisal ? 'active' : ''}" onclick="window.location.href='/my-appraisals'"><i class="bi bi-clipboard-check"></i> <span>My Appraisals</span></li>
            <li class="${isSelf ? 'active' : ''}" onclick="window.location.href='/self-appraisal'"><i class="bi bi-person-badge"></i> <span>Self-Appraisal</span></li>
            <li class="${isGoals ? 'active' : ''}" onclick="window.location.href='/employee-goals'"><i class="bi bi-bullseye"></i> <span>Goals & KRAs</span></li>
            <li class="${isAttend ? 'active' : ''}" onclick="window.location.href='/employee-attendance'"><i class="bi bi-calendar-check"></i> <span>Attendance</span></li>
            <li class="${isLeave ? 'active' : ''}" onclick="window.location.href='/leave-request'"><i class="bi bi-calendar-plus"></i> <span>Leave Request</span></li>
            <li class="${isMyLeaves ? 'active' : ''}" onclick="window.location.href='/requested-leaves'"><i class="bi bi-clock-history"></i> <span>My Leave Requests</span></li>
            <li class="${isTrain ? 'active' : ''}" onclick="window.location.href='/employee-training'"><i class="bi bi-mortarboard"></i> <span>Training</span></li>
        `;
    } else if (role === 'manager') {
        const isDash = page === 'manager-dashboard' || page === 'manager_dashboard.html';
        const isManagerApp = rawPath === '/manager/appraisal' || page === 'manager_appraisal.html' || page === 'manager-appraisal';
        const isTeam = page === 'team-evaluation' || page === 'team_evaluation.html';
        const isReviewApp = page === 'review-appraisal' || page === 'review_appraisal.html' || page.includes('review-employee-appraisal');
        const isReviewAtt = page === 'review-attendance' || page === 'review_attendance.html';
        const isBehaviour = page === 'behaviour-rating' || page === 'behaviour_rating.html';
        const isFeedback = page === 'feedback-360' || page === 'feedback_360.html';
        const isApproveLeaves = page === 'approve-leaves' || page === 'approve_leaves.html';

        const isMyAppraisal = page === 'my-appraisals' || page === 'my_appraisals.html';
        const isSelfAppraisal = page === 'self-appraisal' || page === 'self_appraisal.html' || page === 'appraisal-form' || page === 'appraisal_form.html';
        const isMyGoals = page === 'employee-goals' || page === 'employee_goals.html';
        const isMyAttendance = page === 'employee-attendance' || page === 'employee_attendance.html';
        const isApplyLeave = page === 'leave-request' || page === 'leave_request.html';
        const isMyLeaves = page === 'requested-leaves' || page === 'requested_leaves.html';
        const isMyTraining = page === 'employee-training' || page === 'employee_training.html';

        html = `
            <div class="menu-section-header">Manager Overview</div>
            <li class="${isDash ? 'active' : ''}" onclick="window.location.href='/manager-dashboard'"><i class="bi bi-grid-fill"></i> <span>Dashboard</span></li>
            <li class="${isManagerApp ? 'active' : ''}" onclick="window.location.href='/manager/appraisal'"><i class="bi bi-clipboard-check"></i> <span>Manager Appraisal</span></li>
            <li class="${isTeam ? 'active' : ''}" onclick="window.location.href='/team-evaluation'"><i class="bi bi-people"></i> <span>Team Evaluation</span></li>
            <li class="${isReviewApp ? 'active' : ''}" onclick="window.location.href='/review-appraisal'"><i class="bi bi-clipboard-data"></i> <span>Review Appraisal</span></li>
            <li class="${isReviewAtt ? 'active' : ''}" onclick="window.location.href='/review-attendance'"><i class="bi bi-calendar-range"></i> <span>Review Attendance</span></li>
            <li class="${isBehaviour ? 'active' : ''}" onclick="window.location.href='/behaviour-rating'"><i class="bi bi-star-half"></i> <span>Behaviour Rating</span></li>
            <li class="${isFeedback ? 'active' : ''}" onclick="window.location.href='/feedback-360'"><i class="bi bi-chat-square-text"></i> <span>360 Feedback</span></li>
            <li class="${isApproveLeaves ? 'active' : ''}" onclick="window.location.href='/approve-leaves'"><i class="bi bi-calendar-check"></i> <span>Approve Leaves</span></li>

            <div class="menu-section-header">Self Service</div>
            <li class="${isMyAppraisal ? 'active' : ''}" onclick="window.location.href='/my-appraisals'"><i class="bi bi-award"></i> <span>My Appraisals</span></li>
            <li class="${isSelfAppraisal ? 'active' : ''}" onclick="window.location.href='/self-appraisal'"><i class="bi bi-person-badge"></i> <span>Self-Appraisal</span></li>
            <li class="${isMyGoals ? 'active' : ''}" onclick="window.location.href='/employee-goals'"><i class="bi bi-bullseye"></i> <span>Goals & KRAs</span></li>
            <li class="${isMyAttendance ? 'active' : ''}" onclick="window.location.href='/employee-attendance'"><i class="bi bi-calendar-check"></i> <span>Attendance</span></li>
            <li class="${isApplyLeave ? 'active' : ''}" onclick="window.location.href='/leave-request'"><i class="bi bi-calendar-plus"></i> <span>Leave Request</span></li>
            <li class="${isMyLeaves ? 'active' : ''}" onclick="window.location.href='/requested-leaves'"><i class="bi bi-clock-history"></i> <span>My Leave Requests</span></li>
            <li class="${isMyTraining ? 'active' : ''}" onclick="window.location.href='/employee-training'"><i class="bi bi-mortarboard"></i> <span>Training</span></li>
        `;
    } else if (role === 'hr' || role === 'admin') {
        const isDash = page === 'hr-dashboard' || page === 'hr_dashboard.html' || page === 'admin-dashboard' || page === 'admin_dashboard.html';
        const isPerf = page === 'performance-results' || page === 'performance_results.html' || page === 'employee-performance-details' || page === 'employee_performance_details.html';
        const isTrain = page === 'manage-training' || page === 'manage_training.html' || page === 'training-details' || page === 'training_details.html';
        const isFeedback = page === 'feedback-360' || page === 'feedback_360.html';
        const isApproveLeaves = page === 'approve-leaves' || page === 'approve_leaves.html';
        const isKra = page === 'kra-management' || page === 'kra_management.html' || page.includes('edit-kra') || page === 'add-kra';
        const isKpi = page === 'kpi-management' || page === 'kpi_management.html' || page.includes('edit-kpi') || page === 'add-kpi';
        const isAsgKra = page === 'assign-kra' || page === 'assign_kra.html';
        const isAsgKpi = page === 'assign-kpi' || page === 'assign_kpi.html';
        const isRec = page === 'kpi-records' || page === 'kpi_records.html' || page === 'add-kpi-record';
        const isCycles = page === 'appraisal-cycles' || page === 'appraisal_cycles.html' || page.includes('edit-appraisal-cycle') || page === 'add-appraisal-cycle';
        const isReport = page === 'kra-kpi-report' || page === 'kra_kpi_report.html';

        const isEmpDir = rawPath.startsWith('/admin/employees') || page === 'employees' || page === 'employee_management.html' || page === 'add_employee.html' || page === 'edit_employee.html' || page.includes('employee_profile');
        const isHierarchy = rawPath.startsWith('/admin/hierarchy') || page === 'hierarchy' || page === 'employee_hierarchy.html';
        const isDepts = rawPath.startsWith('/admin/departments') || page === 'departments' || page === 'department_management.html';
        const isBranches = rawPath.startsWith('/admin/branches') || page === 'branches' || page === 'branch_management.html';
        const isDesigs = rawPath.startsWith('/admin/designations') || page === 'designations' || page === 'designation_management.html';
        const isUsers = rawPath.startsWith('/admin/users') || page === 'users' || page === 'user_management.html';

        html = `
            <div class="menu-section-header">HR Administration</div>
            <li class="${isDash ? 'active' : ''}" onclick="window.location.href='/hr-dashboard'"><i class="bi bi-grid-fill"></i> <span>Dashboard</span></li>
            <li class="${isPerf ? 'active' : ''}" onclick="window.location.href='/performance-results'"><i class="bi bi-award"></i> <span>Performance Results</span></li>
            <li class="${isTrain ? 'active' : ''}" onclick="window.location.href='/manage-training'"><i class="bi bi-mortarboard-fill"></i> <span>Manage Training</span></li>
            <li class="${isFeedback ? 'active' : ''}" onclick="window.location.href='/feedback-360'"><i class="bi bi-chat-square-text"></i> <span>360 Feedback</span></li>
            <li class="${isApproveLeaves ? 'active' : ''}" onclick="window.location.href='/approve-leaves'"><i class="bi bi-calendar-check"></i> <span>Approve Leaves</span></li>
            <li class="${isKra ? 'active' : ''}" onclick="window.location.href='/kra-management'"><i class="bi bi-bullseye"></i> <span>KRA Management</span></li>
            <li class="${isKpi ? 'active' : ''}" onclick="window.location.href='/kpi-management'"><i class="bi bi-speedometer2"></i> <span>KPI Management</span></li>
            <li class="${isAsgKra ? 'active' : ''}" onclick="window.location.href='/assign-kra'"><i class="bi bi-person-check"></i> <span>Assign KRA</span></li>
            <li class="${isAsgKpi ? 'active' : ''}" onclick="window.location.href='/assign-kpi'"><i class="bi bi-person-lines-fill"></i> <span>Assign KPI</span></li>
            <li class="${isRec ? 'active' : ''}" onclick="window.location.href='/kpi-records'"><i class="bi bi-speedometer2"></i> <span>KPI Records</span></li>
            <li class="${isCycles ? 'active' : ''}" onclick="window.location.href='/appraisal-cycles'"><i class="bi bi-calendar-range"></i> <span>Appraisal Cycles</span></li>
            <li class="${isReport ? 'active' : ''}" onclick="window.location.href='/kra-kpi-report'"><i class="bi bi-file-earmark-bar-graph"></i> <span>KRA / KPI Report</span></li>

            <div class="menu-section-header">Organization & Staff</div>
            <li class="${isEmpDir ? 'active' : ''}" onclick="window.location.href='/admin/employees'"><i class="bi bi-people-fill"></i> <span>Employee Directory</span></li>
            <li class="${isHierarchy ? 'active' : ''}" onclick="window.location.href='/admin/hierarchy'"><i class="bi bi-diagram-3-fill"></i> <span>Employee Hierarchy</span></li>
            <li class="${isDepts ? 'active' : ''}" onclick="window.location.href='/admin/departments'"><i class="bi bi-building"></i> <span>Departments</span></li>
            <li class="${isBranches ? 'active' : ''}" onclick="window.location.href='/admin/branches'"><i class="bi bi-geo-alt-fill"></i> <span>Branches</span></li>
            <li class="${isDesigs ? 'active' : ''}" onclick="window.location.href='/admin/designations'"><i class="bi bi-award-fill"></i> <span>Designations</span></li>
            <li class="${isUsers ? 'active' : ''}" onclick="window.location.href='/admin/users'"><i class="bi bi-person-badge-fill"></i> <span>User Accounts</span></li>
        `;
    }

    const isProfile = page === 'profile' || page === 'profile.html';
    html += `
        <div class="menu-section-header">Account</div>
        <li class="${isProfile ? 'active' : ''}" onclick="window.location.href='/profile'"><i class="bi bi-person-circle"></i> <span>My Profile</span></li>
        <li onclick="window.location.href='/logout'"><i class="bi bi-box-arrow-right"></i> <span>Sign Out</span></li>
    `;

    menuContainer.innerHTML = html;
    initSidebarScrollTracker();
    restoreSidebarScroll();
    requestAnimationFrame(restoreSidebarScroll);
    setTimeout(restoreSidebarScroll, 50);
}

// --- SIDEBAR SCROLL PERSISTENCE ENGINE ---
function initSidebarScrollTracker() {
    const menuContainer = document.getElementById('sidebarMenu');
    if (!menuContainer) return;

    if (!menuContainer.dataset.scrollTracked) {
        menuContainer.dataset.scrollTracked = 'true';

        menuContainer.addEventListener('scroll', () => {
            sessionStorage.setItem('mtrack_sidebar_scroll', menuContainer.scrollTop);
        }, { passive: true });

        menuContainer.addEventListener('click', (e) => {
            const li = e.target.closest('li');
            if (li) {
                sessionStorage.setItem('mtrack_sidebar_scroll', menuContainer.scrollTop);
            }
        });
    }
}

function restoreSidebarScroll() {
    const menuContainer = document.getElementById('sidebarMenu');
    if (!menuContainer) return;

    const saved = sessionStorage.getItem('mtrack_sidebar_scroll');
    if (saved !== null && !isNaN(parseInt(saved, 10))) {
        menuContainer.scrollTop = parseInt(saved, 10);
    } else {
        const activeLi = menuContainer.querySelector('li.active');
        if (activeLi) {
            const menuHeight = menuContainer.clientHeight;
            const itemTop = activeLi.offsetTop;
            if (itemTop > menuHeight - 80) {
                menuContainer.scrollTop = Math.max(0, itemTop - (menuHeight / 2));
            }
        }
    }
}

window.addEventListener('beforeunload', () => {
    const menuContainer = document.getElementById('sidebarMenu');
    if (menuContainer) {
        sessionStorage.setItem('mtrack_sidebar_scroll', menuContainer.scrollTop);
    }
});

// ============================================================
// PAGE INITIALIZATION
// ============================================================

window.addEventListener(
    'DOMContentLoaded',
    () => {
        initSidebarScrollTracker();
        restoreSidebarScroll();
        requestAnimationFrame(restoreSidebarScroll);
        setTimeout(restoreSidebarScroll, 60);

        const allViews = document.querySelectorAll('.dashboard-view');
        const isMultiViewDemo = allViews.length > 1;

        if (isMultiViewDemo) {
            const activeView = document.querySelector('.dashboard-view.active');
            if (activeView && activeView.id) {
                const viewId = activeView.id.replace('-view', '').toLowerCase();
                if (['employee', 'manager', 'hr'].includes(viewId)) {
                    switchRole(viewId);
                }
            }
        } else {
            const role = detectUserRole();
            updateSidebarMenu(role);
        }


        // ================================================
        // EMPLOYEE DASHBOARD
        // ================================================

        const isEmpDash = window.location.pathname.includes('employee-dashboard') || window.location.pathname.includes('employee_dashboard') || (window.location.pathname === '/' && isMultiViewDemo);
        if (
            isEmpDash &&
            document.getElementById(
                'employee-view'
            )
        ) {

            loadEmployeeDashboardData();
        }

        // ================================================
        // MANAGER DASHBOARD
        // ================================================

        const isMgrDash = window.location.pathname.includes('manager-dashboard') || window.location.pathname.includes('manager_dashboard') || (window.location.pathname === '/' && isMultiViewDemo);
        if (
            isMgrDash &&
            document.getElementById(
                'manager-view'
            )
        ) {

            loadManagerDashboardData();

        }

        // ================================================
        // HR DASHBOARD
        // ================================================

        const isHRDash = window.location.pathname.includes('hr-dashboard') || window.location.pathname.includes('hr_dashboard') || (window.location.pathname === '/' && isMultiViewDemo);
        if (
            isHRDash &&
            document.getElementById(
                'hr-view'
            )
        ) {

            initHRApexCharts();

        }

        // Load profile data dynamically if on profile page
        if (document.getElementById('profileViewContainer') || window.location.pathname.includes('profile')) {
            loadProfilePage();
        }

        // Load notifications globally across all pages
        loadGlobalNotifications();
    }
);

// --- PROFILE PAGE DYNAMIC LOADER ---
async function loadProfilePage() {
    try {
        const response = await fetch('/api/auth/me', {
            method: 'GET',
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        });

        const data = await response.json();
        if (data && data.authenticated && data.user) {
            const role = normalizeRole(data.user.role);
            
            // Update sidebar menu for active role
            updateSidebarMenu(role);

            // Determine user profile object from session/user
            const username = data.user.username || 'User';
            const roleName = data.user.role || (role.charAt(0).toUpperCase() + role.slice(1));
            const userObj = {
                name: data.user.full_name || username,
                roleTitle: data.user.designation || roleName,
                department: data.user.department || 'Not Assigned',
                empId: data.user.employee_code || username.toUpperCase(),
                branch: data.user.branch || 'Head Office',
                email: data.user.email || `${username.toLowerCase()}@muthoot.com`,
                manager: data.user.manager_name || '—',
                joined: data.user.joined_date || '—',
                phone: data.user.phone || '—',
                avatar: ""
            };

            // Update DOM elements if present
            const avatarImg = document.getElementById('profileAvatarImg');
            const fullName = document.getElementById('profileFullName');
            const roleDept = document.getElementById('profileRoleDept');
            const empBadge = document.getElementById('profileEmpBadge');
            const branch = document.getElementById('profileBranch');
            const email = document.getElementById('profileEmail');
            const manager = document.getElementById('profileManager');
            const joined = document.getElementById('profileJoined');

            const inputFullName = document.getElementById('inputFullName');
            const inputEmail = document.getElementById('inputEmail');
            const inputPhone = document.getElementById('inputPhone');
            const inputBranch = document.getElementById('inputBranch');

            if (fullName) fullName.innerText = userObj.name;
            if (roleDept) roleDept.innerText = `${userObj.roleTitle} • ${userObj.department}`;
            if (empBadge) empBadge.innerText = `Employee ID: ${userObj.empId}`;
            if (branch) branch.innerText = userObj.branch;
            if (email) email.innerText = userObj.email;
            if (manager) manager.innerText = userObj.manager;
            if (joined) joined.innerText = userObj.joined;

            if (inputFullName) inputFullName.value = userObj.name;
            if (inputEmail) inputEmail.value = userObj.email;
            if (inputPhone) inputPhone.value = userObj.phone;
            if (inputBranch) inputBranch.value = userObj.branch;

            // Update Topbar badge
            const badgeName = document.querySelector('.user-badge-name');
            const badgeRole = document.querySelector('.user-badge-role');
            if (badgeName) badgeName.innerText = userObj.name;
            if (badgeRole) badgeRole.innerText = userObj.roleTitle;
        }
    } catch (e) {
        console.error('Profile Load Error:', e);
    }
}

// --- GLOBAL NOTIFICATIONS LOADER ---
async function loadGlobalNotifications() {
    try {
        const response = await fetch('/api/notifications/');
        if (!response.ok) return;
        const data = await response.json();
        if (data.success && Array.isArray(data.notifications)) {
            renderNotificationsFromAPI(data.notifications);
        }
    } catch (e) {
        console.error('Global notifications load error:', e);
    }
}

// Global modal cleanup: guarantees that dismissing any Bootstrap modal clears stranded dim backdrops
document.addEventListener('hidden.bs.modal', function () {
    if (!document.querySelector('.modal.show')) {
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('overflow');
        document.body.style.removeProperty('padding-right');
    }
});

