const tableBody = document.getElementById("order-table-body");
const orderCount = document.getElementById("order-count");
const pendingCount = document.getElementById("pending-count");
const revenueEl = document.getElementById("today-revenue");

function loadOrders() {
    fetch("/api/orders")
        .then(res => res.json())
        .then(renderOrders)
        .catch(console.error);
}
let currentOrderId = null;

function openAddItem(orderId) {
    currentOrderId = orderId;

    fetch("/api/menu")
        .then(res => res.json())
        .then(menu => {
            const select = document.getElementById("add-item-select");
            select.innerHTML = "";

            menu.forEach(item => {
                if (item.available) {
                    select.innerHTML += `
                        <option value="${item.id}">
                            ${item.name} – ₹${item.price}
                        </option>`;
                }
            });

            document.getElementById("add-item-qty").value = 1;
            document.getElementById("add-item-modal").classList.remove("hidden");
        });
}

function closeAddItem() {
    document.getElementById("add-item-modal").classList.add("hidden");
}

function confirmAddItem() {
    const itemId = document.getElementById("add-item-select").value;
    const qty = parseInt(document.getElementById("add-item-qty").value);

    if (!itemId || qty < 1) {
        alert("Invalid item");
        return;
    }

    fetch(`/api/order/${currentOrderId}/add-item`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        item_id: itemId,
        qty: qty
    })
})

    .then(() => {
        closeAddItem();
        loadOrders(); // refresh admin table
    });
}

function openEditBill(orderId, tableNo) {
    // reuse your existing menu add/remove logic
    window.location.href = `/menu?add_to_order=${orderId}&table=${tableNo}`;
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

        const itemsArr = Array.isArray(o.items)
            ? o.items
            : JSON.parse(o.items);

        const items = itemsArr
            .map(i => `${i.qty}× ${i.name}`)
            .join(", ");

        tableBody.innerHTML += `
            <tr class="border-b hover:bg-gray-50">
                <td class="p-4 font-bold">Table ${o.table_no}</td>
                <td class="p-4">${items}</td>
                <td class="p-4 font-semibold">₹${o.total}</td>
                <td class="p-4">
                    <span class="badge">${o.status}</span>
                </td>
                <td class="p-4 flex gap-2">
    <a href="/bill/${o.id}"
       class="bg-emerald-600 text-white px-3 py-1 rounded text-sm">
        Bill
    </a>

    <button
        onclick="openEditBill(${o.id}, ${o.table_no})"
        class="bg-blue-600 text-white px-3 py-1 rounded text-sm">
        Edit
    </button>
</td>

            </tr>`;
    });

    pendingCount.innerText = pending;
    revenueEl.innerText = `₹${revenue}`;
}

loadOrders();
setInterval(loadOrders, 3000);
