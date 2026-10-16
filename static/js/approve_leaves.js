async function processLeave(leaveId, status) {

    const actionText = status === "Approved"
        ? "approve"
        : "reject";

    const confirmed = confirm(
        `Are you sure you want to ${actionText} this leave request?`
    );

    if (!confirmed) {
        return;
    }

    try {

        const csrfResponse = await fetch(
            "/api/csrf-token",
            {
                credentials: "same-origin"
            }
        );

        const csrfData = await csrfResponse.json();

        if (!csrfResponse.ok || !csrfData.csrf_token) {
            throw new Error("Unable to obtain CSRF token.");
        }


        const response = await fetch(
            "/approve-leaves",
            {
                method: "POST",

                credentials: "same-origin",

                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-CSRF-Token": csrfData.csrf_token
                },

                body: JSON.stringify({
                    leave_id: leaveId,
                    status: status
                })
            }
        );


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.error || "Unable to process leave request."
            );

        }


        alert(
            data.message ||
            `Leave request ${status.toLowerCase()} successfully.`
        );


        window.location.reload();

    } catch (error) {

        console.error(
            "Leave approval error:",
            error
        );

        alert(
            error.message ||
            "An error occurred while processing the leave request."
        );

    }

}