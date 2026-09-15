document.addEventListener("DOMContentLoaded", function () {
    const deleteLinks = document.querySelectorAll(".delete-link");

    deleteLinks.forEach(function (link) {
        link.addEventListener("click", function (event) {
            const confirmed = confirm("Are you sure you want to delete this poll?");
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });
});

function togglePassword(inputId, button) {
    const passwordInput = document.getElementById(inputId);

    if (!passwordInput) {
        return;
    }

    if (passwordInput.type === "password") {
        passwordInput.type = "text";
        button.textContent = "🙈";
        button.setAttribute("aria-label", "Hide password");
    } else {
        passwordInput.type = "password";
        button.textContent = "👁️";
        button.setAttribute("aria-label", "Show password");
    }
}
