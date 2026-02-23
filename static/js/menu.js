/* ================= GLOBAL ================= */

const menuGrid = document.getElementById("menu-grid");
const params = new URLSearchParams(window.location.search);

let CURRENT_CATEGORY = "";
const ORDER_ID = params.get("add_to_order");
const TABLE_NO = params.get("table");

let ALL_ITEMS = [];

/* ================= SIDEBAR (Mobile) ================= */

function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebar-overlay");

    if (!sidebar) return;

    sidebar.classList.toggle("-translate-x-full");
    overlay.classList.toggle("hidden");
    document.body.classList.toggle("overflow-hidden");
}

/* ================= MODALS ================= */

function openAddModal() {
    document.getElementById("item-modal").classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
}

function closeAddModal() {
    document.getElementById("item-modal").classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
}

function openEditModal(id, name, price, category) {
    document.getElementById("edit-id").value = id;
    document.getElementById("edit-name").value = name;
    document.getElementById("edit-price").value = price;
    document.getElementById("edit-category").value = category;

    document.getElementById("edit-modal").classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
}

function closeEditModal() {
    document.getElementById("edit-modal").classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
}

/* ================= LOAD MENU ================= */

function loadMenu() {
    fetch("/api/menu")
        .then(res => res.json())
        .then(items => {
            ALL_ITEMS = items;
            renderMenu(items);
        })
        .catch(() => {
            menuGrid.innerHTML = `
                <p class="text-red-500 col-span-full">Failed to load menu</p>
            `;
        });
}

/* ================= RENDER MENU (Optimized) ================= */

function renderMenu(items) {

    if (!items.length) {
        menuGrid.innerHTML = `
            <p class="text-gray-500 col-span-full">No matching dishes</p>
        `;
        return;
    }

    let html = "";

    items.forEach(item => {

        const imgSrc = item.image || "/static/no-image.png";

        html += `
            <div class="bg-white rounded-xl shadow overflow-hidden hover:shadow-lg transition">

                <img src="${imgSrc}" class="h-40 w-full object-cover">

                <div class="p-4">
                    <h4 class="font-bold text-lg">${escapeHTML(item.name)}</h4>
                    <p class="text-emerald-600 font-bold">₹${item.price}</p>
                    <p class="text-sm text-gray-500">${item.category}</p>

                    <div class="flex flex-col sm:flex-row gap-2 mt-3">

                        <button onclick="toggleStock(${item.id})"
                            class="px-3 py-2 bg-gray-800 hover:bg-black text-white rounded text-sm">
                            ${item.available ? "Disable" : "Enable"}
                        </button>

                        <button onclick="openEditModal(${item.id}, '${escapeJS(item.name)}', ${item.price}, '${escapeJS(item.category)}')"
                            class="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm">
                            Edit
                        </button>

                        <button onclick="deleteItem(${item.id})"
                            class="px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded text-sm">
                            Delete
                        </button>

                        ${
                            ORDER_ID ? `
                            <button onclick="openAddToOrderModal(${item.id}, '${escapeJS(item.name)}')"
                                class="px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm">
                                + Add to Table ${TABLE_NO}
                            </button>
                            ` : ""
                        }

                    </div>
                </div>
            </div>
        `;
    });

    menuGrid.innerHTML = html;
}

/* ================= SEARCH + FILTER ================= */

function applyFilters() {
    const q = document.getElementById("menuSearch").value.toLowerCase();

    const filtered = ALL_ITEMS.filter(item => {
        const matchName = item.name.toLowerCase().includes(q);
        const matchCategory = !CURRENT_CATEGORY || item.category === CURRENT_CATEGORY;
        return matchName && matchCategory;
    });

    renderMenu(filtered);
}

function setCategory(btn, category) {
    CURRENT_CATEGORY = category;

    document.querySelectorAll(".category-tab")
        .forEach(b => b.classList.remove("active-tab"));

    btn.classList.add("active-tab");

    applyFilters();
}

/* ================= ADD MENU ITEM ================= */

document.getElementById("menu-form").onsubmit = e => {
    e.preventDefault();
    const formData = new FormData(e.target);

    fetch("/api/menu", { method: "POST", body: formData })
        .then(res => {
            if (!res.ok) throw new Error();
            e.target.reset();
            closeAddModal();
            loadMenu();
        })
        .catch(() => alert("Failed to add dish"));
};

/* ================= UPDATE MENU ITEM ================= */

document.getElementById("edit-form").onsubmit = e => {
    e.preventDefault();

    const id = document.getElementById("edit-id").value;
    const formData = new FormData(e.target);

    fetch(`/api/menu/${id}`, {
        method: "PUT",
        body: formData
    })
        .then(res => {
            if (!res.ok) throw new Error();
            closeEditModal();
            loadMenu();
        })
        .catch(() => alert("Failed to update dish"));
};

/* ================= MENU ACTIONS ================= */

function toggleStock(id) {
    fetch(`/api/menu/toggle/${id}`, { method: "POST" })
        .then(() => loadMenu())
        .catch(() => alert("Failed to update item"));
}

function deleteItem(id) {
    if (!confirm("Delete this dish?")) return;

    fetch(`/api/menu/${id}`, { method: "DELETE" })
        .then(() => loadMenu())
        .catch(() => alert("Failed to delete item"));
}

/* ================= ADD TO ORDER ================= */

let selectedItemId = null;
let selectedItemName = "";

function openAddToOrderModal(id, name) {
    selectedItemId = id;
    selectedItemName = name;

    document.getElementById("modal-item-name").innerText = name;
    document.getElementById("modal-qty").value = 1;

    document.getElementById("addToOrderModal").classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
}

function closeAddToOrderModal() {
    document.getElementById("addToOrderModal").classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
}

function confirmAddToOrder() {
    const qty = Number(document.getElementById("modal-qty").value);

    if (!ORDER_ID || qty <= 0) {
        alert("Invalid order or quantity");
        return;
    }

    fetch(`/api/order/${ORDER_ID}/add-item`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: selectedItemId, qty })
    })
        .then(res => res.json())
        .then(data => {
            if (!data.success) {
                alert(data.error || "Failed to add item");
                return;
            }

            closeAddToOrderModal();
            alert(`✅ ${selectedItemName} added to Table ${TABLE_NO}`);
            window.location.href = "/admin";
        })
        .catch(() => alert("Add item failed"));
}

/* ================= QUICK TEMPLATE ================= */

function importTemplate(templateName) {
    fetch("/api/menu/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template: templateName })
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) loadMenu();
            else alert(data.error || "Failed to import menu");
        })
        .catch(() => alert("Something went wrong"));
}

/* ================= HELPERS ================= */

function escapeHTML(str) {
    return str.replace(/[&<>"']/g, function(m) {
        return ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        })[m];
    });
}

function escapeJS(str) {
    return str.replace(/'/g, "\\'");
}

/* ================= INIT ================= */

loadMenu();