const ordersContainer = document.getElementById("orders-container");
const additionsContainer = document.getElementById("additions");
const pendingCount = document.getElementById("pending-count");

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

/* ================= ORDERS ================= */

function renderOrders(orders) {
    ordersContainer.innerHTML = "";

    const activeOrders = orders.filter(o =>
        ["Received", "Preparing", "Ready"].includes(o.status)
    );

    pendingCount.innerText = activeOrders.length;

    if (!activeOrders.length) {
        ordersContainer.innerHTML = `
            <div class="text-gray-400 text-xl">
                No active orders 👨‍🍳
            </div>
        `;
        return;
    }

    activeOrders.forEach(o => {
        const items = Array.isArray(o.items)
            ? o.items
            : JSON.parse(o.items || "[]");

        const itemHtml = items
            .map(i => `${i.qty} × ${i.name}`)
            .join("<br>");

        const nextStatus =
            o.status === "Received" ? "Preparing" :
            o.status === "Preparing" ? "Ready" :
            "Served";

        ordersContainer.innerHTML += `
            <div class="bg-white w-80 rounded-xl shadow-xl text-gray-900">
                <div class="p-4 border-b">
                    <h2 class="text-3xl font-black">TABLE ${o.table_no}</h2>
                    <p class="text-xs text-gray-400">ORDER #${o.id}</p>
                </div>

                <div class="p-4 text-sm">${itemHtml}</div>

                <div class="p-4 bg-gray-50">
                    <button
                        onclick="updateStatus(${o.id}, '${nextStatus}')"
                        class="w-full py-3 bg-emerald-600 text-white rounded-lg font-bold">
                        Mark ${nextStatus}
                    </button>
                </div>
            </div>
        `;
    });
}

function loadKitchenOrders() {
    fetch("/api/kitchen/orders")
        .then(res => res.json())
        .then(renderOrders)
        .catch(err => console.error("Kitchen orders error:", err));
}

/* ================= ADDITIONS (WITH SOUND) ================= */

function renderAdditions(additions) {
    if (!additions.length) {
        additionsContainer.innerHTML =
            `<p class="text-gray-400">No new additions</p>`;
        return;
    }

    additionsContainer.innerHTML = additions.map(a => `
        <div class="bg-red-600 text-white p-4 rounded-lg mb-3">
            <h3 class="font-black">TABLE ${a.table_no}</h3>
            <p>${a.qty} × ${a.item_name}</p>
            <button
                onclick="markAdditionDone(${a.id})"
                class="mt-3 bg-black px-4 py-2 rounded">
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
        const res = await fetch(`/api/order/${orderId}/status`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status })
        });

        if (!res.ok) throw new Error();

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
        })
        .catch(() => alert("Failed to update addition"));
}

/* ================= INIT ================= */

loadKitchenOrders();
loadKitchenAdditions();

setInterval(loadKitchenOrders, 3000);
setInterval(loadKitchenAdditions, 3000);
