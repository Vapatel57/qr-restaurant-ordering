const menuGrid = document.getElementById("menu-grid");
const params = new URLSearchParams(window.location.search);

const ORDER_ID = params.get("add_to_order");
const TABLE_NO = params.get("table");

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

/* ================= LOAD MENU ================= */

function loadMenu(category = null) {
    fetch("/api/menu")
        .then(res => res.json())
        .then(items => {
            menuGrid.innerHTML = "";

            if (!items.length) {
                menuGrid.innerHTML = `
                    <p class="text-gray-500 col-span-full">No menu items found</p>
                `;
                return;
            }

            items
                .filter(i => !category || i.category === category)
                .forEach(item => {
                    const imgSrc = item.image
                        ? item.image
                        : "/static/no-image.png";

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
                                        <button onclick="openAddToOrderModal(${item.id}, '${item.name}', ${item.price})"
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
        })
        .catch(err => {
            console.error(err);
            menuGrid.innerHTML = `
                <p class="text-red-500 col-span-full">Failed to load menu</p>
            `;
        });
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

/* ================= ADD TO ORDER (ADMIN BILL EDIT) ================= */

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
        body: JSON.stringify({
            item_id: selectedItemId,
            qty: qty
        })
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
        .catch(err => {
            console.error(err);
            alert("Add item failed");
        });
}
function importTemplate(templateName) {
    fetch("/api/menu/import", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            template: templateName
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert(data.error || "Failed to import menu");
        }
    })
    .catch(err => {
        console.error(err);
        alert("Something went wrong");
    });
}
async function searchMenu() {
    const q = document.getElementById("menuSearch").value;
    const category = document.getElementById("categoryFilter").value;

    const res = await fetch(
        `/api/menu?search=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}`
    );
    const data = await res.json();

    renderMenu(data); // your existing render function
}
/* ================= INIT ================= */

loadMenu();
