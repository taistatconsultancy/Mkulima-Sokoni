(function () {
  const root = document.getElementById("screenRoot");
  const roleTabs = document.getElementById("roleTabs");
  const rolePill = document.getElementById("rolePill");
  const stickyCta = document.getElementById("stickyCta");
  const stickyActionBtn = document.getElementById("stickyActionBtn");

  let currentRole = localStorage.getItem("userRole") || "buyer";
  let deferredInstallPrompt = null;
  const refreshStamp = {};
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  let mobileChat = { view: "list", convo: null, messages: [], sending: false };
  let chatPollTimer = null;
  let prevTotalUnread = 0;
  let PUBLIC_CONFIG = { gps_enabled: true };

  function formatKsh(n) {
    return `KSh ${Number(n || 0).toLocaleString()}`;
  }

  function cardMedia(url, alt) {
    if (!url) return "";
    return `<div class="card-media"><img src="${url}" alt="${alt || "Image"}" loading="lazy" /></div>`;
  }

  function card(title, body, meta) {
    return `<article class="card">
      <div class="row"><strong>${title}</strong>${meta ? `<span class="meta">${meta}</span>` : ""}</div>
      ${body}
    </article>`;
  }

  function panel(title, sub, body) {
    return `<section class="panel">
      <h3 class="panel-title">${title}</h3>
      ${sub ? `<div class="panel-sub">${sub}</div>` : ""}
      ${body}
    </section>`;
  }

  function updateRoleTabs() {
    rolePill.textContent = `Role: ${currentRole}`;
    [...roleTabs.querySelectorAll(".tab-btn")].forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.role === currentRole);
    });
  }

  function updateSticky(label, onClick) {
    if (!label || !onClick) {
      stickyCta.style.display = "none";
      stickyActionBtn.onclick = null;
      return;
    }
    stickyCta.style.display = "";
    stickyActionBtn.textContent = label;
    stickyActionBtn.onclick = onClick;
  }

  function setLastUpdated(key) {
    refreshStamp[key] = new Date().toLocaleTimeString("en-KE");
  }

  function getLastUpdated(key) {
    return refreshStamp[key] ? `Last updated ${refreshStamp[key]}` : "";
  }

  function onlineBanner(show) {
    const id = "offlineNotice";
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement("div");
      el.id = id;
      el.className = "offline";
      el.textContent = "Offline mode: live data may be unavailable.";
      root.prepend(el);
    }
    el.classList.toggle("show", !!show);
  }

  function installGuidance() {
    if (!isIOS || window.matchMedia("(display-mode: standalone)").matches) return "";
    return `<div class="notice">On iPhone: tap Share, then "Add to Home Screen" to install.</div>`;
  }

  function computeTotalUnread(convos) {
    return (convos || []).reduce((sum, c) => sum + Number(c.unread_count || 0), 0);
  }

  async function loadPublicConfig() {
    try {
      const cfg = await MobileAPI.publicConfig();
      if (cfg && typeof cfg === "object") PUBLIC_CONFIG = { ...PUBLIC_CONFIG, ...cfg };
    } catch (_) {}
    return PUBLIC_CONFIG;
  }

  function setRoleUnreadBadge(total) {
    try {
      rolePill.textContent = total > 0 ? `Role: ${currentRole} • ${total} unread` : `Role: ${currentRole}`;
    } catch (_) {}
  }

  function showNewMsgNotice(delta) {
    if (!delta || delta <= 0) return;
    const id = "newMsgNotice";
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement("div");
      el.id = id;
      el.className = "notice";
      el.style.marginBottom = "10px";
      root.prepend(el);
    }
    el.textContent = `New messages (${delta}).`;
    clearTimeout(el.__t);
    el.__t = setTimeout(() => { try { el.remove(); } catch (_) {} }, 4500);
  }

  function stopChatPolling() {
    if (chatPollTimer) clearTimeout(chatPollTimer);
    chatPollTimer = null;
  }

  function startChatPolling() {
    stopChatPolling();
    const tick = async () => {
      try {
        if (document.hidden) return;
        if (mobileChat.view === "thread" && mobileChat.convo) return;
        const data = await MobileAPI.chat.conversations(currentRole);
        const list = data?.conversations || [];
        const total = computeTotalUnread(list);
        const delta = Math.max(0, total - (prevTotalUnread || 0));
        prevTotalUnread = total;
        setRoleUnreadBadge(total);
        showNewMsgNotice(delta);
      } catch (_) {
        // ignore polling errors
      } finally {
        chatPollTimer = setTimeout(tick, 15000 + Math.floor(Math.random() * 2000));
      }
    };
    chatPollTimer = setTimeout(tick, 7000);
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderThread(convo) {
    const title = escapeHtml(convo?.farm_name || convo?.buyer_email || "Conversation");
    const msgs = mobileChat.messages || [];
    const body = msgs.length
      ? msgs.map((m) => {
          const mine = String(m.sender_user_id || "") === String(MobileAPI.getUser()?.id || "");
          const cls = mine ? "me" : "them";
          const pending = m.__pending ? " pending" : "";
          const failed = m.__failed ? " failed" : "";
          const meta = m.created_at ? `<div class="meta">${escapeHtml(m.created_at)}</div>` : "";
          return `<div class="bubble ${cls}${pending}${failed}">${escapeHtml(m.body)}${meta}</div>`;
        }).join("")
      : `<div class="notice">No messages yet.</div>`;

    return `
      <section class="panel">
        <div class="row" style="justify-content:flex-start;gap:10px;">
          <button class="btn" id="backToConvos">← Conversations</button>
          <strong style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${title}</strong>
        </div>
        <div class="chat-thread" id="chatThread">${body}</div>
        <div class="row" style="gap:10px;align-items:flex-end;margin-top:10px;">
          <textarea class="input" id="chatInput" placeholder="Type a message…" rows="2" style="flex:1;"></textarea>
          <button class="btn primary" id="chatSendBtn" ${mobileChat.sending ? "disabled" : ""}>${mobileChat.sending ? "Sending…" : "Send"}</button>
        </div>
      </section>
    `;
  }

  function wireThreadHandlers() {
    const back = document.getElementById("backToConvos");
    const sendBtn = document.getElementById("chatSendBtn");
    const input = document.getElementById("chatInput");
    const thread = document.getElementById("chatThread");
    const scrollBottom = () => { try { thread.scrollTop = thread.scrollHeight; } catch (_) {} };
    scrollBottom();

    if (back) {
      back.addEventListener("click", async () => {
        mobileChat.view = "list";
        mobileChat.convo = null;
        mobileChat.messages = [];
        await renderRole();
      });
    }

    if (sendBtn && input) {
      sendBtn.addEventListener("click", async () => {
        const text = String(input.value || "").trim();
        if (!text || mobileChat.sending || !mobileChat.convo) return;
        mobileChat.sending = true;

        const pending = {
          body: text,
          __pending: true,
          __failed: false,
          sender_user_id: String(MobileAPI.getUser()?.id || ""),
          created_at: "pending…",
        };
        mobileChat.messages = [...(mobileChat.messages || []), pending];
        root.className = "content";
        root.innerHTML = renderThread(mobileChat.convo);
        wireThreadHandlers();

        try {
          input.value = "";
          await MobileAPI.chat.send(mobileChat.convo.id, text);
          const t = await MobileAPI.chat.thread(mobileChat.convo.id);
          mobileChat.messages = (t?.messages || []).slice().reverse().map((m) => ({ ...m }));
        } catch (e) {
          pending.__pending = false;
          pending.__failed = true;
          pending.created_at = "failed";
          alert(e.message || "Failed to send");
        } finally {
          mobileChat.sending = false;
          root.className = "content";
          root.innerHTML = renderThread(mobileChat.convo);
          wireThreadHandlers();
        }
      });
    }
  }

  async function renderBuyer() {
    root.className = "content two-col";
    root.innerHTML = panel("Buyer Dashboard", "Browse, cart, checkout, and messaging.", `<div class="notice">Loading buyer data…</div>`);
    updateSticky("Checkout Cart", async () => {
      try { await MobileAPI.buyer.checkout(); await renderBuyer(); }
      catch (e) { alert(e.message || "Checkout failed"); }
    });

    try {
      const [products, cart, tenders, orders, convos] = await Promise.all([
        MobileAPI.buyer.products(),
        MobileAPI.buyer.cart(),
        MobileAPI.buyer.tenders(),
        MobileAPI.buyer.orders(),
        MobileAPI.chat.conversations("buyer")
      ]);
      const totalUnread = computeTotalUnread(convos?.conversations || []);
      prevTotalUnread = Math.max(prevTotalUnread, totalUnread);
      setRoleUnreadBadge(totalUnread);
      setLastUpdated("buyer");
      root.innerHTML = installGuidance() +
        panel("Marketplace", getLastUpdated("buyer"), `<div class="stack">
          ${(products || []).slice(0, 6).map((p) => card(
            p.name || "Product",
            `${cardMedia(p.image_url, p.name)}
             <div class="meta">${p.category || "Category"} • ${p.location || "Kenya"}</div>
             <div class="row"><span class="amount">${formatKsh(p.price || p.price_min || 0)}</span></div>
             <div class="actions">
               <button class="btn primary" data-add="${p.id}">Add</button>
               <a class="btn" href="../frontend/product-detail.html?id=${encodeURIComponent(p.id)}">View →</a>
             </div>`
          )).join("") || `<div class="notice">No products available.</div>`}
        </div>`) +
        panel("Cart", `Items: ${cart?.summary?.item_count || 0}`, `<div class="stack">
          ${(cart?.items || []).slice(0, 5).map((i) => card(
            i.product_name || "Item",
            `<div class="row"><span>${i.quantity || 0} ${i.measurement_metric || ""}</span><span class="amount">${formatKsh(i.line_total || 0)}</span></div>`,
            i.seller_name || "Seller"
          )).join("") || `<div class="notice">Cart is empty.</div>`}
        </div>`) +
        panel("Tenders", `Open: ${(tenders?.tenders || []).filter(t => t.status === "open").length}`, `<div class="stack">
          ${(tenders?.tenders || []).slice(0, 4).map((t) => card(
            t.title || "Tender",
            `<div class="meta">${t.product_category || "General"} • bids: ${t.bid_count || 0}</div>`
          )).join("") || `<div class="notice">No tenders yet.</div>`}
        </div>`) +
        panel("Orders", `Total: ${(orders?.orders || []).length}`, `<div class="stack">
          ${(orders?.orders || []).slice(0, 4).map((o) => card(
            `#${String(o.id || "").slice(0, 8)}`,
            `<div class="row"><span>${o.status || "pending"}</span><span class="amount">${formatKsh(o.total_amount || 0)}</span></div>`
          )).join("") || `<div class="notice">No orders yet.</div>`}
        </div>`) +
        panel("Messages", `Conversations: ${(convos?.conversations || []).length}`, `<div class="stack" id="mobileConvoList">
          ${(convos?.conversations || []).slice(0, 8).map((c) => card(
            `${escapeHtml(c.farm_name || "Conversation")}${c.unread_count ? ` (${Number(c.unread_count)})` : ""}`,
            `<div class="meta">${escapeHtml(c.last_message_body || "No messages yet.")}</div>
             <div class="actions"><button class="btn primary" data-open-convo="${escapeHtml(c.id)}">Open</button></div>`
          )).join("") || `<div class="notice">No conversations yet.</div>`}
        </div>`);

      root.querySelectorAll("[data-add]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            await MobileAPI.buyer.addToCart(btn.getAttribute("data-add"), 1);
            await renderBuyer();
          } catch (e) { alert(e.message || "Failed to add to cart"); }
        });
      });

      root.querySelectorAll("[data-open-convo]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.getAttribute("data-open-convo");
          const convo = (convos?.conversations || []).find((x) => String(x.id) === String(id));
          if (!convo) return;
          try {
            mobileChat.view = "thread";
            mobileChat.convo = convo;
            mobileChat.sending = false;
            const t = await MobileAPI.chat.thread(convo.id);
            mobileChat.messages = (t?.messages || []).slice().reverse().map((m) => ({ ...m }));
            root.className = "content";
            root.innerHTML = renderThread(convo);
            wireThreadHandlers();
          } catch (e) {
            alert(e.message || "Failed to load messages");
          }
        });
      });
    } catch (e) {
      root.innerHTML = panel("Buyer Dashboard", "", `<div class="notice">Could not load data: ${e.message || "Unknown error"}</div>`);
    }
  }

  async function renderFarmer() {
    root.className = "content two-col";
    root.innerHTML = panel("Farmer Dashboard", "Products, orders, tenders, and messages.", `<div class="notice">Loading farmer data…</div>`);
    updateSticky("Open Messages", async () => renderFarmer());
    try {
      const [products, orders, tenders, convos] = await Promise.all([
        MobileAPI.seller.products(),
        MobileAPI.seller.orders(),
        MobileAPI.seller.tenders(),
        MobileAPI.chat.conversations("farmer")
      ]);
      const totalUnread = computeTotalUnread(convos?.conversations || []);
      prevTotalUnread = Math.max(prevTotalUnread, totalUnread);
      setRoleUnreadBadge(totalUnread);
      setLastUpdated("farmer");
      root.innerHTML = installGuidance() +
        panel("Products", getLastUpdated("farmer"), `<div class="stack">
          ${(products || []).slice(0, 6).map((p) => card(
            p.name || "Product",
            `${cardMedia(p.image_url, p.name)}
             <div class="row"><span>${p.status || "draft"}</span><span class="amount">${formatKsh(p.price || p.price_min || 0)}</span></div>
             <div class="actions">
               <a class="btn" href="../frontend/product-detail.html?id=${encodeURIComponent(p.id)}">View →</a>
             </div>`
          )).join("") || `<div class="notice">No products yet.</div>`}
        </div>`) +
        panel("Orders", `Total: ${(orders?.orders || []).length}`, `<div class="stack">
          ${(orders?.orders || []).slice(0, 6).map((o) => card(
            `#${String(o.id || "").slice(0, 8)}`,
            `<div class="row"><span>${o.status || "pending"}</span><span class="amount">${formatKsh(o.total_amount || 0)}</span></div>`,
            o.buyer_email || "Buyer"
          )).join("") || `<div class="notice">No orders yet.</div>`}
        </div>`) +
        panel("Tenders", "", `<div class="stack">
          ${(tenders?.tenders || []).slice(0, 5).map((t) => card(
            t.title || "Tender",
            `<div class="meta">${t.status || "open"} • ${t.location || "Any location"}</div>`
          )).join("") || `<div class="notice">No tenders available.</div>`}
        </div>`) +
        panel("Messages", `Conversations: ${(convos?.conversations || []).length}`, `<div class="stack">
          ${(convos?.conversations || []).slice(0, 8).map((c) => card(
            `${escapeHtml(c.buyer_email || c.farm_name || "Conversation")}${c.unread_count ? ` (${Number(c.unread_count)})` : ""}`,
            `<div class="meta">${escapeHtml(c.last_message_body || "No messages yet.")}</div>
             <div class="actions"><button class="btn primary" data-open-convo="${escapeHtml(c.id)}">Open</button></div>`
          )).join("") || `<div class="notice">No conversations yet.</div>`}
        </div>`);

      root.querySelectorAll("[data-open-convo]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.getAttribute("data-open-convo");
          const convo = (convos?.conversations || []).find((x) => String(x.id) === String(id));
          if (!convo) return;
          try {
            mobileChat.view = "thread";
            mobileChat.convo = convo;
            mobileChat.sending = false;
            const t = await MobileAPI.chat.thread(convo.id);
            mobileChat.messages = (t?.messages || []).slice().reverse().map((m) => ({ ...m }));
            root.className = "content";
            root.innerHTML = renderThread(convo);
            wireThreadHandlers();
          } catch (e) {
            alert(e.message || "Failed to load messages");
          }
        });
      });
    } catch (e) {
      root.innerHTML = panel("Farmer Dashboard", "", `<div class="notice">Could not load data: ${e.message || "Unknown error"}</div>`);
    }
  }

  async function renderDealer() {
    root.className = "content two-col";
    root.innerHTML = panel("Agro-dealer Dashboard", "Inventory, orders, and tenders.", `<div class="notice">Loading agro-dealer data…</div>`);
    updateSticky("Refresh Inventory", async () => renderDealer());
    try {
      const [products, orders, tenders] = await Promise.all([
        MobileAPI.seller.products(),
        MobileAPI.seller.orders(),
        MobileAPI.seller.tenders()
      ]);
      setLastUpdated("dealer");
      root.innerHTML = installGuidance() +
        panel("Inventory", getLastUpdated("dealer"), `<div class="stack">
          ${(products || []).slice(0, 6).map((p) => card(
            p.name || "Product",
            `${cardMedia(p.image_url, p.name)}
             <div class="row"><span>${p.quantity || 0} ${p.measurement_metric || ""}</span><span>${p.status || "draft"}</span></div>
             <div class="actions">
               <a class="btn" href="../frontend/product-detail.html?id=${encodeURIComponent(p.id)}">View →</a>
             </div>`
          )).join("") || `<div class="notice">No products yet.</div>`}
        </div>`) +
        panel("Orders", "", `<div class="stack">
          ${(orders?.orders || []).slice(0, 6).map((o) => card(
            `#${String(o.id || "").slice(0, 8)}`,
            `<div class="row"><span>${o.status || "pending"}</span><span class="amount">${formatKsh(o.total_amount || 0)}</span></div>`
          )).join("") || `<div class="notice">No orders yet.</div>`}
        </div>`) +
        panel("Tenders", "", `<div class="stack">
          ${(tenders?.tenders || []).slice(0, 5).map((t) => card(
            t.title || "Tender",
            `<div class="meta">${t.status || "open"} • ${(t.product_category || "General")}</div>`
          )).join("") || `<div class="notice">No tenders found.</div>`}
        </div>`);
    } catch (e) {
      root.innerHTML = panel("Agro-dealer Dashboard", "", `<div class="notice">Could not load data: ${e.message || "Unknown error"}</div>`);
    }
  }

  async function renderRole() {
    updateRoleTabs();
    if (currentRole === "buyer") return renderBuyer();
    if (currentRole === "farmer") return renderFarmer();
    return renderDealer();
  }

  function wireTabs() {
    roleTabs.addEventListener("click", (e) => {
      const btn = e.target.closest(".tab-btn");
      if (!btn) return;
      currentRole = btn.dataset.role;
      localStorage.setItem("userRole", currentRole);
      setRoleUnreadBadge(0);
      renderRole();
    });
  }

  function registerPWA() {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/mobile-app/sw.js").catch(() => {});
    }
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredInstallPrompt = e;
      updateSticky("Install App", async () => {
        if (!deferredInstallPrompt) return;
        deferredInstallPrompt.prompt();
        await deferredInstallPrompt.userChoice;
        deferredInstallPrompt = null;
        renderRole();
      });
    });
  }

  function wireConnectivity() {
    const apply = () => onlineBanner(!navigator.onLine);
    window.addEventListener("online", apply);
    window.addEventListener("offline", apply);
    apply();
  }

  function wireVisibilityRefresh() {
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        stopChatPolling();
        return;
      }
      renderRole();
      startChatPolling();
    });
  }

  wireTabs();
  wireConnectivity();
  wireVisibilityRefresh();
  registerPWA();
  loadPublicConfig().then(() => {
    // In future GPS-related mobile features should check PUBLIC_CONFIG.gps_enabled.
  });
  renderRole();
  startChatPolling();
})();
