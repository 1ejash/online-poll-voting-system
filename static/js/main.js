document.addEventListener("DOMContentLoaded", function () {
    const deleteLinks = document.querySelectorAll(".delete-link");

    deleteLinks.forEach(function (link) {
        link.addEventListener("click", function (event) {
            const confirmed = confirm(
                "Are you sure you want to delete this poll?"
            );

            if (!confirmed) {
                event.preventDefault();
            }
        });
    });
});
