document.addEventListener("DOMContentLoaded", () => {
    loadTeamEvaluations();

    const evaluationForm =
        document.getElementById("evaluationForm");

    if (evaluationForm) {
        evaluationForm.addEventListener(
            "submit",
            submitTeamEvaluation
        );
    }
});


let teamEvaluations = [];


async function loadTeamEvaluations() {

    const tbody =
        document.getElementById("teamEvaluationTableBody");

    if (!tbody) {
        return;
    }

    try {

        const response =
            await fetch("/api/manager/team-evaluations", {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json"
                }
            });

        const data =
            await response.json();

        if (!response.ok || !data.success) {

            throw new Error(
                data.message ||
                "Unable to load team evaluations."
            );
        }

        teamEvaluations =
            data.evaluations || [];

        renderTeamEvaluations();

    } catch (error) {

        console.error(
            "Team evaluation loading error:",
            error
        );

        tbody.innerHTML = `
            <tr>
                <td colspan="7"
                    class="text-center text-danger py-4">
                    Failed to load team evaluations.
                </td>
            </tr>
        `;
    }
}


function renderTeamEvaluations() {

    const tbody =
        document.getElementById(
            "teamEvaluationTableBody"
        );

    if (!tbody) {
        return;
    }

    if (teamEvaluations.length === 0) {

        tbody.innerHTML = `
            <tr>
                <td colspan="7"
                    class="text-center text-muted py-4">
                    No team evaluations found.
                </td>
            </tr>
        `;

        return;
    }


    tbody.innerHTML =
        teamEvaluations.map(evaluation => {

            const status =
                evaluation.status || "Pending";

            const isCompleted =
                status.toLowerCase() === "approved";

            return `
                <tr>

                    <td>
                        <strong>
                            ${escapeHtml(
                                evaluation.employee_name
                            )}
                        </strong>

                        <br>

                        <small class="text-muted">
                            ${escapeHtml(
                                evaluation.employee_code
                            )}
                        </small>
                    </td>

                    <td>
                        ${escapeHtml(
                            evaluation.designation
                        )}
                    </td>

                    <td>
                        ${Number(
                            evaluation.self_score || 0
                        ).toFixed(2)} / 5
                    </td>

                    <td>
                        <span class="rating-pill">
                            ${Number(
                                evaluation.manager_score || 0
                            ).toFixed(2)} ⭐
                        </span>
                    </td>

                    <td>
                        ${Number(
                            evaluation.behaviour_score || 0
                        ).toFixed(2)} / 5
                    </td>

                    <td>
                        <span class="badge-muthoot ${
                            isCompleted
                                ? "completed"
                                : "review"
                        }">
                            ${escapeHtml(status)}
                        </span>
                    </td>

                    <td>

                        <button
                            class="btn btn-sm btn-muthoot"
                            onclick="openEvaluation(
                                ${evaluation.appraisal_id}
                            )">

                            <i class="bi bi-pencil-square me-1"></i>

                            ${
                                isCompleted
                                    ? "View"
                                    : "Evaluate"
                            }

                        </button>

                    </td>

                </tr>
            `;

        }).join("");
}


function openEvaluation(appraisalId) {

    const evaluation =
        teamEvaluations.find(
            item =>
                Number(item.appraisal_id) ===
                Number(appraisalId)
        );

    if (!evaluation) {

        alert("Evaluation record not found.");

        return;
    }

    window.currentEvaluation =
        evaluation;


    const employeeName =
        document.getElementById(
            "evaluationEmployeeName"
        );

    if (employeeName) {
        employeeName.textContent =
            evaluation.employee_name;
    }


    document.getElementById(
        "performanceRating"
    ).value = evaluation.manager_score
        ? Number(evaluation.manager_score).toFixed(1)
        : "";

    document.getElementById(
        "behaviourRating"
    ).value = evaluation.behaviour_score
        ? Number(evaluation.behaviour_score).toFixed(1)
        : "";

    document.getElementById(
        "managerRemarks"
    ).value = "";


    const modalElement =
        document.getElementById(
            "evalModal"
        );

    const modal =
        bootstrap.Modal.getOrCreateInstance(
            modalElement
        );

    modal.show();
}


async function submitTeamEvaluation(event) {

    event.preventDefault();

    const evaluation = window.currentEvaluation;

    if (!evaluation) {
        alert("Select an employee evaluation first.");
        return;
    }

    const performanceScore = Number(
        document.getElementById("performanceRating").value
    );
    const behaviourScore = Number(
        document.getElementById("behaviourRating").value
    );
    const remarks = document.getElementById("managerRemarks").value.trim();

    if (
        !Number.isFinite(performanceScore)
        || !Number.isFinite(behaviourScore)
        || performanceScore < 1
        || performanceScore > 5
        || behaviourScore < 1
        || behaviourScore > 5
    ) {
        alert("Performance and behaviour scores must be between 1 and 5.");
        return;
    }

    try {
        const csrfToken = await getCsrfToken();
        const response = await fetch(
            `/api/manager/team-evaluations/${evaluation.appraisal_id}`,
            {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken
                },
                body: JSON.stringify({
                    performance_score: performanceScore,
                    behaviour_score: behaviourScore,
                    remarks: remarks
                })
            }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(
                data.message || "Unable to save the evaluation."
            );
        }

        bootstrap.Modal.getInstance(
            document.getElementById("evalModal")
        ).hide();

        await loadTeamEvaluations();

    } catch (error) {
        console.error("Team evaluation save error:", error);
        alert(error.message || "Unable to save the evaluation.");
    }
}


function escapeHtml(value) {

    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
