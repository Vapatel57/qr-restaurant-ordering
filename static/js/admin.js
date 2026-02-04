const tableBody = document.getElementById("order-table-body");
const orderCount = document.getElementById("order-count");
const pendingCount = document.getElementById("pending-count");
const revenueEl = document.getElementById("today-revenue");

/* ================= LOAD ORDERS ================= */

function loadOrders() {
    fetch("/api/orders")
        .then(res => res.json())
        .then(renderOrders)
        .catch(err => console.error("Load error:", err));
}

/* ================= ACTIONS ================= */

function openEditBill(orderId) {
    window.location.href = `/admin/order/${orderId}/edit`;
}

function generateBillAndClose(orderId) {
    if (!confirm("Generate bill and close this table?")) return;

    fetch(`/api/order/${orderId}/close`, { method: "POST" })
        .then(r => r.json())
        .then(r => {
            if (r.success) {
                window.location.href = `/bill/${orderId}`;
            } else {
                alert("Failed to close order");
            }
        })
        .catch(() => alert("Server error"));
}

/* ================= RENDER TABLE ================= */

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
        const status = (o.status || "").toLowerCase().trim();
        const isClosed = status === "closed";

        if (!isClosed) pending++;
        if (isClosed) revenue += Number(o.total || 0);

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
                    ${
                        !isClosed
                        ? `
                        <button
                            onclick="openEditBill(${o.id})"
                            class="bg-blue-600 text-white px-3 py-1 rounded text-sm">
                            Edit
                        </button>

                        <button
                            onclick="generateBillAndClose(${o.id})"
                            class="bg-red-600 text-white px-3 py-1 rounded text-sm">
                            Generate Bill & Close
                        </button>
                        `
                        : `
                        <span class="text-gray-400 font-semibold text-sm">
                            Closed
                        </span>
                        `
                    }
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
