const ordersContainer = document.getElementById("orders-container");
const additionsContainer = document.getElementById("additions");
const pendingCount = document.getElementById("pending-count");

const lastOrderIds = new Set();
const lastAdditionIds = new Set();
const updatingOrders = new Set();

/* ================= SOUND ================= */

function playSound() {
    const sound = document.getElementById("orderSound");
    if (sound) {
        sound.currentTime = 0;
        sound.play().catch(() => {});
    }
}

/* ================= STATUS COLORS ================= */

function getStatusColor(status) {
    if (status === "Received") return "border-yellow-500";
    if (status === "Preparing") return "border-blue-500";
    if (status === "Ready") return "border-emerald-500";
    return "border-gray-500";
}

/* ================= RENDER ORDERS ================= */

function renderOrders(orders) {
    const activeOrders = orders.filter(o =>
        ["Received", "Preparing", "Ready"].includes(o.status)
    );

    pendingCount.innerText = activeOrders.length;

    if (!activeOrders.length) {
        ordersContainer.innerHTML =
            `<div class="text-gray-400 text-xl">No active orders 👨‍🍳</div>`;
        return;
    }

    ordersContainer.innerHTML = activeOrders.map(o => {

        const items = Array.isArray(o.items)
            ? o.items
            : JSON.parse(o.items || "[]");

        const itemHtml = items
            .map(i => `<div class="mb-1">${i.qty} × ${i.name}</div>`)
            .join("");

        const nextStatus =
            o.status === "Received" ? "Preparing" :
            o.status === "Preparing" ? "Ready" :
            "Served";

        return `
            <div class="bg-white w-96 rounded-xl shadow-xl text-gray-900 border-t-8 ${getStatusColor(o.status)}">

                <div class="p-5 border-b">
                    <h2 class="text-4xl font-black">
                        TABLE ${o.table_no}
                    </h2>
                    <p class="text-sm text-gray-500">
                        ORDER #${o.id}
                    </p>
                    <p class="text-xs font-bold mt-1">
                        ${o.status}
                    </p>
                </div>

                <div class="p-5 text-lg font-semibold leading-relaxed max-h-72 overflow-y-auto">
                    ${itemHtml}
                </div>

                <div class="p-5 bg-gray-100">
                    <button
                        onclick="updateStatus(${o.id}, '${nextStatus}')"
                        class="w-full py-4 bg-emerald-600 text-white rounded-lg text-lg font-bold hover:bg-emerald-700">
                        Mark ${nextStatus}
                    </button>
                </div>

            </div>
        `;
    }).join("");
}

/* ================= LOAD ORDERS ================= */

function loadKitchenOrders() {
    fetch("/api/kitchen/orders")
        .then(res => res.json())
        .then(orders => {

            let hasNew = false;

            orders.forEach(o => {
                if (!lastOrderIds.has(o.id)) {
                    lastOrderIds.add(o.id);
                    hasNew = true;
                }
            });

            if (hasNew && orders.length > 0) {
                playSound();
            }

            renderOrders(orders);
        })
        .catch(err => console.error("Kitchen orders error:", err));
}

/* ================= ADDITIONS ================= */

function renderAdditions(additions) {
    if (!additions.length) {
        additionsContainer.innerHTML =
            `<p class="text-gray-500">No new additions</p>`;
        return;
    }

    additionsContainer.innerHTML = additions.map(a => `
        <div class="bg-red-600 text-white p-4 rounded-lg shadow">
            <h3 class="text-lg font-black">
                TABLE ${a.table_no}
            </h3>
            <p class="text-sm mt-1">
                ${a.qty} × ${a.item_name}
            </p>

            <button
                onclick="markAdditionDone(${a.id})"
                class="mt-4 bg-black w-full py-2 rounded font-bold">
                Mark Preparing
            </button>
        </div>
    `).join("");
}

function loadKitchenAdditions() {
    fetch("/api/kitchen/additions")
        .then(res => res.json())
        .then(additions => {

            let hasNew = false;

            additions.forEach(a => {
                if (!lastAdditionIds.has(a.id)) {
                    lastAdditionIds.add(a.id);
                    hasNew = true;
                }
            });

            if (hasNew) playSound();

            renderAdditions(additions);
        })
        .catch(err => console.error("Kitchen additions error:", err));
}

/* ================= UPDATE STATUS ================= */

async function updateStatus(orderId, status) {
    if (updatingOrders.has(orderId)) return;
    updatingOrders.add(orderId);

    try {
        await fetch(`/api/order/${orderId}/status`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status })
        });

        loadKitchenOrders();
    } catch {
        alert("Failed to update order status");
    } finally {
        updatingOrders.delete(orderId);
    }
}

function markAdditionDone(id) {
    fetch(`/api/kitchen/addition/${id}/status`, { method: "POST" })
        .then(() => {
            loadKitchenAdditions();
            loadKitchenOrders();
        });
}

/* ================= INIT ================= */

loadKitchenOrders();
loadKitchenAdditions();

setInterval(loadKitchenOrders, 3000);
setInterval(loadKitchenAdditions, 3000);