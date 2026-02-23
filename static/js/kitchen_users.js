/* ================================
   HELPERS
================================ */

function showAlert(message, type = "error") {
    const color = type === "success"
        ? "bg-emerald-600"
        : "bg-red-600";

    const toast = document.createElement("div");
    toast.className = `
        fixed bottom-6 right-6 z-50
        ${color} text-white px-4 py-3
        rounded-lg shadow-lg text-sm
        animate-fade
    `;
    toast.innerText = message;

    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}


/* ================================
   CREATE USER
================================ */

async function createUser() {
    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");
    const button = document.querySelector("#kitchen-form button");

    const email = emailInput.value.trim();
    const password = passwordInput.value.trim();

    if (!email || !password) {
        showAlert("Email and password required");
        return;
    }

    if (password.length < 6) {
        showAlert("Password must be at least 6 characters");
        return;
    }

    button.disabled = true;
    button.innerText = "Creating...";

    try {
        const res = await fetch("/api/kitchen-users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();

        if (!data.success) {
            showAlert(data.error || "Failed to create user");
            button.disabled = false;
            button.innerText = "Create";
            return;
        }

        // Add new row dynamically (no reload)
        addUserRow(data.user_id || Date.now(), email);

        emailInput.value = "";
        passwordInput.value = "";

        showAlert("Kitchen user created successfully", "success");

    } catch (err) {
        console.error(err);
        showAlert("Server error");
    }

    button.disabled = false;
    button.innerText = "Create";
}


/* ================================
   DELETE USER
================================ */

async function deleteUser(id) {
    if (!confirm("Delete this kitchen user?")) return;

    try {
        const res = await fetch(`/api/kitchen-users/${id}`, {
            method: "DELETE"
        });

        const data = await res.json();

        if (!data.success) {
            showAlert("Failed to delete user");
            return;
        }

        // Remove row without reload
        const row = document.querySelector(`[data-user-id="${id}"]`);
        if (row) row.remove();

        showAlert("User deleted", "success");

    } catch {
        showAlert("Server error");
    }
}


/* ================================
   ADD ROW DYNAMICALLY
================================ */

function addUserRow(id, email) {
    const table = document.getElementById("user-table");

    const row = document.createElement("tr");
    row.className = "border-t";
    row.setAttribute("data-user-id", id);

    row.innerHTML = `
        <td class="p-4">${email}</td>
        <td class="p-4 text-center">
            <button onclick="deleteUser(${id})"
                class="text-red-600 hover:underline font-semibold">
                Delete
            </button>
        </td>
    `;

    table.appendChild(row);
}


/* ================================
   OPTIONAL: Toast Animation
================================ */

const style = document.createElement("style");
style.innerHTML = `
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.animate-fade {
    animation: fadeInUp 0.25s ease;
}
`;
document.head.appendChild(style);