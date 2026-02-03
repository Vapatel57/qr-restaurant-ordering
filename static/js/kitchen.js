const ordersContainer = document.getElementById("orders-container");
const additionsContainer = document.getElementById("additions");
const pendingCount = document.getElementById("pending-count");

const updatingOrders = new Set();

function renderOrders(orders) {
    ordersContainer.innerHTML = "";

    const active = orders.filter(o =>
        o.status === "Received" ||
        o.status === "Preparing" ||
        o.status === "Ready"
    );

    pendingCount.innerText = active.length;

    if (active.length === 0) {
        ordersContainer.innerHTML = `
            <div class="text-gray-400 text-xl">
                No active orders 👨‍🍳
            </div>`;
        return;
    }

    active.forEach(o => {
        const items = JSON.parse(o.items)
            .map(i => `${i.qty} × ${i.name}`)
            .join("<br>");

        const next =
            o.status === "Received" ? "Preparing" :
            o.status === "Preparing" ? "Ready" :
            "Served";

        ordersContainer.innerHTML += `
            <div class="bg-white w-80 rounded-xl shadow-xl">
                <div class="p-4 border-b">
                    <h2 class="text-3xl font-black">TABLE ${o.table_no}</h2>
                    <p class="text-xs text-gray-400">ORDER #${o.id}</p>
                </div>
                <div class="p-4 text-sm">${items}</div>
                <div class="p-4 bg-gray-50">
                    <button onclick="updateStatus(${o.id}, '${next}')"
                        class="w-full py-3 bg-emerald-600 text-white rounded-lg font-bold">
                        Mark ${next}
                    </button>
                </div>
            </div>`;
    });
}

function loadKitchenOrders() {
    fetch("/api/kitchen/orders")
        .then(res => {
            if (!res.ok) throw new Error("Forbidden or failed");
            return res.json();
        })
        .then(renderOrders)
        .catch(err => console.error("Kitchen orders error:", err));
}



async function updateStatus(orderId, status) {
    if (updatingOrders.has(orderId)) return;
    updatingOrders.add(orderId);

    await fetch(`/api/order/${orderId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
    });

    updatingOrders.delete(orderId);
    loadKitchenOrders();
}

function loadAdditions() {
    fetch("/api/kitchen/additions")
        .then(res => res.json())
        .then(additions => {
            additionsContainer.innerHTML = additions.length
                ? additions.map(a => `
                    <div class="bg-red-600 text-white p-4 rounded-lg mb-3">
                        <h3 class="font-black">TABLE ${a.table_no}</h3>
                        <p>${a.qty} × ${a.item_name}</p>
                        <button onclick="markAdditionDone(${a.id})"
                            class="mt-3 bg-black px-4 py-2 rounded">
                            Mark Preparing
                        </button>
                    </div>`).join("")
                : `<p class="text-gray-400">No new additions</p>`;
        });
}

function markAdditionDone(id) {
    fetch(`/api/kitchen/addition/${id}/status`, { method: "POST" })
        .then(loadAdditions);
}

loadKitchenOrders();
loadAdditions();
setInterval(loadKitchenOrders, 3000);
setInterval(loadAdditions, 3000);
