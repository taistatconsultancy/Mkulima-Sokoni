(function () {
  const isProduction = !["localhost", "127.0.0.1"].includes(window.location.hostname);
  const API_BASE = isProduction ? "/api" : "http://localhost:5000/api";

  function getUser() {
    try { return JSON.parse(localStorage.getItem("user") || "{}"); }
    catch { return {}; }
  }

  function getFirebaseUid() {
    const u = getUser();
    return u.firebase_uid || u.id || "";
  }

  async function apiJson(url, opts) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(opts?.headers || {}) },
      ...opts
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.message || `Request failed (${res.status})`);
    return data;
  }

  const API = {
    base: API_BASE,
    getFirebaseUid,
    getUser,
    apiJson,
    buyer: {
      products: () => apiJson(`${API_BASE}/products?status=active`),
      cart: () => apiJson(`${API_BASE}/cart?firebase_uid=${encodeURIComponent(getFirebaseUid())}`),
      addToCart: (productId, quantity) => apiJson(`${API_BASE}/cart/items`, {
        method: "POST",
        body: JSON.stringify({ firebase_uid: getFirebaseUid(), product_id: productId, quantity })
      }),
      checkout: () => apiJson(`${API_BASE}/cart/checkout`, {
        method: "POST",
        body: JSON.stringify({ firebase_uid: getFirebaseUid() })
      }),
      orders: () => apiJson(`${API_BASE}/orders/buyer?firebase_uid=${encodeURIComponent(getFirebaseUid())}`),
      tenders: () => apiJson(`${API_BASE}/tenders?firebase_uid=${encodeURIComponent(getFirebaseUid())}`)
    },
    seller: {
      orders: () => apiJson(`${API_BASE}/orders/seller?firebase_uid=${encodeURIComponent(getFirebaseUid())}`),
      tenders: () => apiJson(`${API_BASE}/tenders?firebase_uid=${encodeURIComponent(getFirebaseUid())}`),
      products: () => apiJson(`${API_BASE}/products/farmer/${encodeURIComponent(getFirebaseUid())}`)
    },
    chat: {
      conversations: (role) => apiJson(`${API_BASE}/chat/conversations?firebase_uid=${encodeURIComponent(getFirebaseUid())}&role=${encodeURIComponent(role)}`)
    }
  };

  window.MobileAPI = API;
})();
