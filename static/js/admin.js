const tableBody = document.getElementById("order-table-body");
const mobileContainer = document.getElementById("mobile-orders");
const orderCount = document.getElementById("order-count");
const pendingCount = document.getElementById("pending-count");
const revenueEl = document.getElementById("today-revenue");

/* SIDEBAR */
function toggleSidebar() {
    document.getElementById("sidebar").classList.toggle("-translate-x-full");
    document.getElementById("sidebar-overlay").classList.toggle("hidden");
}

/* LOAD ORDERS */
function loadOrders() {
    tableBody.innerHTML = `
    <tr>
        <td colspan="5" class="p-6 text-center text-gray-400 animate-pulse">
            Loading orders...
        </td>
    </tr>`;

    fetch("/api/orders")
        .then(res => res.json())
        .then(renderOrders)
        .catch(err => console.error(err));
}

/* ACTIONS */

function openEditBill(orderId) {
    window.location.href = `/admin/order/${orderId}/edit`;
}

function generateBillAndClose(orderId) {
    if (!confirm("Generate bill and close this table?")) return;

    fetch(`/api/order/${orderId}/close`, { method: "POST" })
        .then(r => r.json())
        .then(r => {
            if (r.success) window.location.href = `/bill/${orderId}`;
            else alert("Failed to close order");
        });
}

/* RENDER */

function renderOrders(orders) {
    tableBody.innerHTML = "";
    mobileContainer.innerHTML = "";

    let pending = 0;
    let revenue = 0;

    if (!orders.length) {
        tableBody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-gray-400">No orders yet 🍽️</td></tr>`;
        mobileContainer.innerHTML = `<div class="p-6 text-center text-gray-400">No orders yet 🍽️</div>`;
        orderCount.innerText = 0;
        pendingCount.innerText = 0;
        revenueEl.innerText = "₹0";
        return;
    }

    orders.forEach(o => {
        const status = (o.status || "").toLowerCase();
        const isClosed = status === "closed";

        if (!isClosed) pending++;
        if (isClosed) revenue += Number(o.total || 0);

        const itemsArr = Array.isArray(o.items) ? o.items : JSON.parse(o.items || "[]");
        const itemsText = itemsArr.map(i => `${i.qty}× ${i.name}`).join(", ");

        /* DESKTOP TABLE */
        tableBody.innerHTML += `
        <tr class="border-b hover:bg-gray-50">
            <td class="p-4 font-bold">Table ${o.table_no}</td>
            <td class="p-4 text-sm">${itemsText}</td>
            <td class="p-4 font-semibold">₹${o.total}</td>
            <td class="p-4">${o.status}</td>
            <td class="p-4 flex gap-2">
            ${
            !isClosed
            ? `
            <button onclick="openEditBill(${o.id})" class="bg-blue-600 text-white px-4 py-2 rounded text-sm">Edit</button>
            <button onclick="generateBillAndClose(${o.id})" class="bg-red-600 text-white px-4 py-2 rounded text-sm">Close</button>`
            : `<span class="text-gray-400">Closed</span>`
            }
            </td>
        </tr>`;

        /* MOBILE CARD */
        mobileContainer.innerHTML += `
        <div class="p-4">
            <div class="flex justify-between items-center">
                <div class="font-bold text-lg">Table ${o.table_no}</div>
                <div class="text-xs px-2 py-1 rounded bg-gray-100">${o.status}</div>
            </div>

            <div class="text-sm text-gray-600 mt-2">${itemsText}</div>

            <div class="flex justify-between items-center mt-3">
                <div class="font-bold text-emerald-600">₹${o.total}</div>

                ${
                !isClosed
                ? `
                <div class="flex gap-2">
                    <button onclick="openEditBill(${o.id})" class="bg-blue-600 text-white px-4 py-2 rounded text-sm">Edit</button>
                    <button onclick="generateBillAndClose(${o.id})" class="bg-red-600 text-white px-4 py-2 rounded text-sm">Close</button>
                </div>`
                : `<span class="text-gray-400 text-sm">Closed</span>`
                }
            </div>
        </div>`;
    });

    orderCount.innerText = orders.length;
    pendingCount.innerText = pending;
    revenueEl.innerText = `₹${revenue}`;
}

/* HISTORY MODAL */

function openHistory() {
    document.getElementById("history-modal").classList.remove("hidden");
}
function closeHistory() {
    document.getElementById("history-modal").classList.add("hidden");
}

async function loadHistory() {
    const date = document.getElementById("history-date").value;
    if (!date) return alert("Select date");

    const res = await fetch(`/admin/orders/by-date?date=${date}`);
    const data = await res.json();

    let html = `<div class="font-semibold mb-2">Orders: ${data.count} | Revenue: ₹${data.revenue}</div><ul class="space-y-2">`;

    data.orders.forEach(o => {
        html += `<li class="border rounded p-2">
        <div><b>Table:</b> ${o.table_no}</div>
        <div><b>Total:</b> ₹${o.total}</div>
        <div><b>Status:</b> ${o.status}</div>
        </li>`;
    });

    html += `</ul>`;
    document.getElementById("history-result").innerHTML = html;
}

/* INIT */
loadOrders();
setInterval(loadOrders, 3000);
