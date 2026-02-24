import React from "react";
import axios from "@/utils/api";
import Layout from "@/components/Layout";

// ── Notifications Page ────────────────────────────────────────────────────────
// =============================================================================
const NotificationsPage = () => {
  const [notifications, setNotifications] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [filter, setFilter] = React.useState("all");

  const load = async () => {
    try {
      const params = filter === "unread" ? { unread_only: true } : {};
      const res = await axios.get("/notifications", { params });
      setNotifications(res.data);
    } catch {} finally { setLoading(false); }
  };

  React.useEffect(() => { load(); }, [filter]);

  const markRead = async (id) => {
    try {
      await axios.put(`/notifications/${id}/read`);
      setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
    } catch {}
  };

  const markAllRead = async () => {
    try {
      await axios.put("/notifications/read-all");
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {}
  };

  const typeIcon = (t) => {
    const map = { request_received: "📋", match_created: "🤝", payment_completed: "💳", alternative_offered: "🔄", subscription_created: "⭐", kvkk_request: "🔒" };
    return map[t] || "🔔";
  };

  if (loading) return <Layout><div className="page-center"><span className="loading-spin" /></div></Layout>;

  return (
    <Layout>
      <div className="page-header">
        <h1 className="page-title">🔔 Bildirimler</h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <select value={filter} onChange={(e) => setFilter(e.target.value)} style={{ padding: "0.4rem", borderRadius: "0.4rem", border: "1px solid #d1d5db" }}>
            <option value="all">Tümü</option>
            <option value="unread">Okunmamış</option>
          </select>
          <button className="btn-ghost btn-sm" onClick={markAllRead}>Tümünü Okundu Yap</button>
        </div>
      </div>

      {notifications.length === 0 ? (
        <div className="empty-state"><div className="empty-state-icon">🔔</div><div className="empty-state-title">Bildirim yok</div></div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {notifications.map((n) => (
            <div key={n.id} className="card" style={{ padding: "1rem", display: "flex", gap: "1rem", alignItems: "flex-start", opacity: n.is_read ? 0.7 : 1, borderLeft: n.is_read ? "3px solid #e5e7eb" : "3px solid #2563eb", cursor: "pointer" }} onClick={() => !n.is_read && markRead(n.id)}>
              <span style={{ fontSize: "1.5rem" }}>{typeIcon(n.type)}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{n.title}</div>
                <div style={{ color: "#6b7c93", fontSize: "0.85rem" }}>{n.message}</div>
                <div style={{ color: "#9ca3af", fontSize: "0.75rem", marginTop: "0.25rem" }}>{new Date(n.created_at).toLocaleString("tr-TR")}</div>
              </div>
              {!n.is_read && <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#2563eb", flexShrink: 0, marginTop: "6px" }} />}
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
};

export default NotificationsPage;
