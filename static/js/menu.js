const menuGrid = document.getElementById("menu-grid");
const params = new URLSearchParams(window.location.search);
let CURRENT_CATEGORY = "";
const ORDER_ID = params.get("add_to_order");
const TABLE_NO = params.get("table");

let ALL_ITEMS = [];

/* ================= MODALS ================= */

function openAddModal() {
    document.getElementById("item-modal").classList.remove("hidden");
}

function closeAddModal() {
    document.getElementById("item-modal").classList.add("hidden");
}

function openEditModal(id, name, price, category) {
    document.getElementById("edit-id").value = id;
    document.getElementById("edit-name").value = name;
    document.getElementById("edit-price").value = price;
    document.getElementById("edit-category").value = category;
    document.getElementById("edit-modal").classList.remove("hidden");
}

function closeEditModal() {
    document.getElementById("edit-modal").classList.add("hidden");
}

/* ================= LOAD MENU (FETCH ONCE) ================= */

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

/* ================= RENDER MENU ================= */

function renderMenu(items) {
    menuGrid.innerHTML = "";

    if (!items.length) {
        menuGrid.innerHTML = `
            <p class="text-gray-500 col-span-full">No matching dishes</p>
        `;
        return;
    }

    items.forEach(item => {
        const imgSrc = item.image || "/static/no-image.png";

        menuGrid.innerHTML += `
            <div class="bg-white rounded-xl shadow overflow-hidden">
                <img src="${imgSrc}" class="h-40 w-full object-cover">

                <div class="p-4">
                    <h4 class="font-bold">${item.name}</h4>
                    <p class="text-emerald-600 font-bold">₹${item.price}</p>
                    <p class="text-sm text-gray-500">${item.category}</p>

                    <div class="flex flex-wrap gap-2 mt-3">
                        <button onclick="toggleStock(${item.id})"
                            class="px-3 py-1 bg-gray-800 text-white rounded">
                            ${item.available ? "Disable" : "Enable"}
                        </button>

                        <button onclick="openEditModal(${item.id}, '${item.name}', ${item.price}, '${item.category}')"
                            class="px-3 py-1 bg-blue-600 text-white rounded">
                            Edit
                        </button>

                        <button onclick="deleteItem(${item.id})"
                            class="px-3 py-1 bg-red-600 text-white rounded">
                            Delete
                        </button>

                        ${
                            ORDER_ID ? `
                            <button onclick="openAddToOrderModal(${item.id}, '${item.name}')"
                                class="px-3 py-1 bg-emerald-600 text-white rounded">
                                + Add to Table ${TABLE_NO}
                            </button>
                            ` : ""
                        }
                    </div>
                </div>
            </div>
        `;
    });
}

/* ================= SEARCH + CATEGORY FILTER ================= */

function applyFilters() {
    const q = document.getElementById("menuSearch").value.toLowerCase();

    const filtered = ALL_ITEMS.filter(item => {
        const matchName = item.name.toLowerCase().includes(q);
        const matchCategory = !CURRENT_CATEGORY || item.category === CURRENT_CATEGORY;
        return matchName && matchCategory;
    });

    renderMenu(filtered);
}
function filterByCategory(category = "") {
    CURRENT_CATEGORY = category;
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
}

function closeAddToOrderModal() {
    document.getElementById("addToOrderModal").classList.add("hidden");
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

/* ================= QUICK MENU TEMPLATE ================= */

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

/* ================= INIT ================= */

loadMenu();
