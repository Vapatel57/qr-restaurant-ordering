const tableBody = document.getElementById("order-table-body");
const orderCount = document.getElementById("order-count");
const pendingCount = document.getElementById("pending-count");
const revenueEl = document.getElementById("today-revenue");

function nextStatus(status) {
    if (status === "Received") return "Preparing";
    if (status === "Preparing") return "Ready";
    if (status === "Ready") return "Served";
    return status;
}

function loadOrders() {
    fetch("/api/orders")
        .then(res => res.json())
        .then(renderOrders)
        .catch(console.error);
}

function renderOrders(orders) {
    tableBody.innerHTML = "";
    orderCount.innerText = orders.length;

    let pending = 0;
    let revenue = 0;

    if (orders.length === 0) {
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
        if (o.status !== "Served") pending++;
        if (o.status === "Served") revenue += Number(o.total);

        const items = JSON.parse(o.items)
            .map(i => `${i.qty}× ${i.name}`)
            .join(", ");

        tableBody.innerHTML += `
            <tr class="border-b hover:bg-gray-50">
                <td class="p-4 font-bold">Table ${o.table_no}</td>
                <td class="p-4">${items}</td>
                <td class="p-4 font-semibold">₹${o.total}</td>
                <td class="p-4">${o.status}</td>
                <td class="p-4 flex gap-2">
                    <button onclick="updateStatus(${o.id}, '${nextStatus(o.status)}')"
                        class="bg-gray-800 text-white px-3 py-1 rounded text-sm">
                        Mark ${nextStatus(o.status)}
                    </button>
                    <a href="/bill/${o.id}"
                       class="bg-emerald-600 text-white px-3 py-1 rounded text-sm">
                        Bill
                    </a>
                </td>
            </tr>`;
    });

    pendingCount.innerText = pending;
    revenueEl.innerText = `₹${revenue}`;
}

function updateStatus(orderId, status) {
    fetch(`/api/order/${orderId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
    }).then(loadOrders);
}

loadOrders();
setInterval(loadOrders, 3000);
