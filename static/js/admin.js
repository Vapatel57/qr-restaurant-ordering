const tableBody = document.getElementById("order-table-body");
const orderCount = document.getElementById("order-count");
const pendingCount = document.getElementById("pending-count");
const revenueEl = document.getElementById("today-revenue");

/* ================= LOAD ORDERS ================= */

function loadOrders() {
    fetch("/api/orders")
        .then(res => {
            if (!res.ok) throw new Error("Failed to load orders");
            return res.json();
        })
        .then(renderOrders)
        .catch(err => console.error("Admin load error:", err));
}

/* ================= EDIT BILL ================= */

function openEditBill(orderId) {
    window.location.href = `/admin/order/${orderId}/edit`;
}
function closeOrder(orderId) {
    if (!confirm("Generate final bill and close this table?")) return;

    fetch(`/api/order/${orderId}/close`, { method: "POST" })
        .then(r => r.json())
        .then(r => {
            if (r.success) loadOrders();
            else alert("Failed to close order");
        });
}

/* ================= RENDER ORDERS ================= */

function renderOrders(orders) {
    tableBody.innerHTML = "";
    orderCount.innerText = orders.length;

    let pending = 0;
    let revenue = 0;

    if (!orders.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="p-6 text-center text-gray-400">
                    No orders yet 🍽️
                </td>
            </tr>`;
        pendingCount.innerText = 0;
        revenueEl.innerText = "₹0";
        return;
    }

    orders.forEach(o => {
        if (o.status !== "Closed") pending++;
        if (o.status === "Closed") revenue += Number(o.total || 0);

        const itemsArr = Array.isArray(o.items)
            ? o.items
            : JSON.parse(o.items || "[]");

        const itemsText = itemsArr.length
            ? itemsArr.map(i => `${i.qty}× ${i.name}`).join(", ")
            : "<span class='text-gray-400'>No items</span>";

        tableBody.innerHTML += `
            <tr class="border-b hover:bg-gray-50">
                <td class="p-4 font-bold">Table ${o.table_no}</td>

                <td class="p-4 text-sm">${itemsText}</td>

                <td class="p-4 font-semibold">₹${o.total}</td>

                <td class="p-4">
                    <span class="badge">${o.status}</span>
                </td>

                <td class="p-4 flex gap-2">
    <button
        onclick="openEditBill(${o.id})"
        class="bg-blue-600 text-white px-3 py-1 rounded text-sm">
        Edit
    </button>

    ${o.status !== "Closed" ? `
    <button
        onclick="closeOrder(${o.id})"
        class="bg-red-600 text-white px-3 py-1 rounded text-sm">
        Generate Bill & Close
    </button>` : ""}
</td>


            </tr>
        `;
    });

    pendingCount.innerText = pending;
    revenueEl.innerText = `₹${revenue}`;
}

/* ================= INIT ================= */

loadOrders();
setInterval(loadOrders, 3000);
