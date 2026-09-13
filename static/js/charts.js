document.addEventListener("DOMContentLoaded", function () {
    const dataElements = document.querySelectorAll(".result-data");

    if (!dataElements.length || typeof Chart === "undefined") {
        return;
    }

    const labels = [];
    const voteData = [];

    dataElements.forEach(function (item) {
        labels.push(item.dataset.label);
        voteData.push(Number(item.dataset.votes));
    });

    new Chart(document.getElementById("barChart"), {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: "Number of Votes",
                data: voteData,
                backgroundColor: [
                    "#2563eb",
                    "#4f46e5",
                    "#0ea5e9",
                    "#7c3aed",
                    "#16a34a",
                    "#ea580c"
                ],
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });

    new Chart(document.getElementById("pieChart"), {
        type: "pie",
        data: {
            labels: labels,
            datasets: [{
                data: voteData,
                backgroundColor: [
                    "#2563eb",
                    "#4f46e5",
                    "#0ea5e9",
                    "#7c3aed",
                    "#16a34a",
                    "#ea580c"
                ],
                borderWidth: 2,
                borderColor: "#ffffff"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
});
