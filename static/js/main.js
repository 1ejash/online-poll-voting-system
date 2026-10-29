

document.addEventListener("DOMContentLoaded", function () {
    // -------------------------------------------------------------
    // Mobile Navigation Toggle
    // -------------------------------------------------------------
    const navToggle = document.getElementById("navToggle");
    const navMenu = document.getElementById("navMenu");

    if (navToggle && navMenu) {
        navToggle.addEventListener("click", function () {
            navMenu.classList.toggle("show");
            const expanded = navMenu.classList.contains("show");
            navToggle.setAttribute("aria-expanded", expanded);
        });
    }

    // -------------------------------------------------------------
    // Live Gmail Validator for Auth Forms
    // -------------------------------------------------------------
    const emailInputs = document.querySelectorAll("input[type='email'], input[name='email']");
    const gmailRegex = /^[a-zA-Z0-9](?:[a-zA-Z0-9.]{4,28}[a-zA-Z0-9])?@gmail\.com$/i;

    emailInputs.forEach(input => {
        // Create hint element if not present
        let hint = input.parentNode.querySelector(".gmail-hint");
        if (!hint && input.closest(".form-group")) {
            hint = document.createElement("div");
            hint.className = "gmail-hint";
            input.closest(".form-group").appendChild(hint);
        }

        input.addEventListener("input", function () {
            const val = this.value.trim();
            if (!val) {
                if (hint) hint.innerHTML = "";
                return;
            }

            if (gmailRegex.test(val)) {
                if (hint) {
                    hint.className = "gmail-hint valid";
                    hint.innerHTML = "✓ Valid verified Gmail address";
                }
                this.style.borderColor = "var(--success)";
            } else if (!val.toLowerCase().includes("@gmail.com")) {
                if (hint) {
                    hint.className = "gmail-hint invalid";
                    hint.innerHTML = "⚠️ Only genuine @gmail.com accounts are permitted to access this site";
                }
                this.style.borderColor = "var(--danger)";
            } else {
                if (hint) {
                    hint.className = "gmail-hint invalid";
                    hint.innerHTML = "⚠️ Please enter a valid Gmail username (6-30 letters, numbers, or dots)";
                }
                this.style.borderColor = "var(--warning)";
            }
        });
    });

    // -------------------------------------------------------------
    // Vote option highlighting: radios are exclusive; checkboxes are independent.
    // Do not clear other selected cards when a checkbox changes.
    // -------------------------------------------------------------
    const voteOptions = document.querySelectorAll(".vote-option-label");
    voteOptions.forEach(option => {
        const input = option.querySelector(".vote-option-input");
        if (!input) return;

        const syncSelectedState = () => {
            option.classList.toggle("selected", input.checked);
            if (input.type === "radio" && input.checked) {
                voteOptions.forEach(otherOption => {
                    if (otherOption === option) return;
                    const otherInput = otherOption.querySelector(".vote-option-input");
                    if (otherInput && otherInput.type === "radio" && otherInput.name === input.name) {
                        otherOption.classList.toggle("selected", otherInput.checked);
                    }
                });
            }
        };

        input.addEventListener("change", syncSelectedState);
        // Clicking the option card toggles its native input; keep styling in sync.
        syncSelectedState();
    });

    // -------------------------------------------------------------
    // Live Poll Search & Filtering
    // -------------------------------------------------------------
    const searchInput = document.getElementById("pollSearchInput");
    if (searchInput) {
        searchInput.addEventListener("input", function () {
            const filter = this.value.toLowerCase().trim();
            const cards = document.querySelectorAll(".poll-card");
            let visibleCount = 0;

            cards.forEach(card => {
                const title = card.querySelector("h2") ? card.querySelector("h2").innerText.toLowerCase() : "";
                const desc = card.querySelector(".poll-description") ? card.querySelector(".poll-description").innerText.toLowerCase() : "";

                if (title.includes(filter) || desc.includes(filter)) {
                    card.style.display = "";
                    visibleCount++;
                } else {
                    card.style.display = "none";
                }
            });

            const noMatchesMsg = document.getElementById("noMatchesFound");
            if (noMatchesMsg) {
                noMatchesMsg.style.display = (visibleCount === 0 && cards.length > 0) ? "block" : "none";
            }
        });
    }

    // -------------------------------------------------------------
    // Alert Banner Dismissal
    // -------------------------------------------------------------
    document.querySelectorAll(".alert-close").forEach(btn => {
        btn.addEventListener("click", function () {
            const alert = this.closest(".alert");
            if (alert) {
                alert.style.opacity = "0";
                alert.style.transform = "translateY(-10px)";
                setTimeout(() => alert.remove(), 250);
            }
        });
    });
});

// -------------------------------------------------------------
// Global Helper Functions
// -------------------------------------------------------------
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;

    if (input.type === "password") {
        input.type = "text";
        btn.innerHTML = "🙈";
        btn.setAttribute("aria-label", "Hide password");
    } else {
        input.type = "password";
        btn.innerHTML = "👁️";
        btn.setAttribute("aria-label", "Show password");
    }
}

function confirmDeletePoll(pollQuestion) {
    return confirm(`Are you sure you want to permanently delete the poll:\n\n"${pollQuestion}"?\n\nAll votes recorded for this poll will also be deleted.`);
}

// -------------------------------------------------------------
// Dynamic Option Manager for Create / Edit Poll Forms
// -------------------------------------------------------------
function addPollOption() {
    const container = document.getElementById("dynamicOptionsContainer");
    if (!container) return;

    const currentCount = container.querySelectorAll(".dynamic-option-item").length;
    if (currentCount >= 6) {
        alert("A poll can have at most 6 voting options.");
        return;
    }

    const nextIndex = currentCount + 1;
    const newItem = document.createElement("div");
    newItem.className = "dynamic-option-item";
    newItem.id = `optionItem_${nextIndex}`;
    newItem.innerHTML = `
        <span class="option-badge-num">${nextIndex}</span>
        <input
            type="text"
            id="option${nextIndex}"
            name="option${nextIndex}"
            class="form-input"
            placeholder="Enter option ${nextIndex} text"
            required
        >
        <button
            type="button"
            class="btn btn-secondary btn-sm"
            onclick="removePollOption(${nextIndex})"
            title="Remove Option"
        >
            ✕
        </button>
    `;
    container.appendChild(newItem);
    renumberOptions();
}

function removePollOption(index) {
    const container = document.getElementById("dynamicOptionsContainer");
    if (!container) return;

    const items = container.querySelectorAll(".dynamic-option-item");
    if (items.length <= 2) {
        alert("A poll requires at least 2 voting options.");
        return;
    }

    const item = document.getElementById(`optionItem_${index}`);
    if (item) {
        item.remove();
        renumberOptions();
    }
}

function renumberOptions() {
    const container = document.getElementById("dynamicOptionsContainer");
    if (!container) return;

    const items = container.querySelectorAll(".dynamic-option-item");
    items.forEach((item, idx) => {
        const num = idx + 1;
        item.id = `optionItem_${num}`;
        const badge = item.querySelector(".option-badge-num");
        if (badge) badge.innerText = num;

        const input = item.querySelector("input");
        if (input) {
            input.id = `option${num}`;
            input.name = `option${num}`;
            input.placeholder = `Enter option ${num} text`;
        }

        const rmBtn = item.querySelector("button");
        if (rmBtn) {
            rmBtn.setAttribute("onclick", `removePollOption(${num})`);
        }
    });
}
