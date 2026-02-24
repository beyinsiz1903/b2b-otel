import React from "react";
import { Link, useLocation } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useWS } from "@/contexts/WSContext";

const Layout = ({ children }) => {
  const { hotel, logout } = useAuth();
  const location = useLocation();
  const { dark, toggle } = useTheme();
  const ws = useWS();
  const isActive = (path) => location.pathname.startsWith(path) ? "active" : "";

  // WebSocket ile gerçek zamanlı bildirim sayısı kullan, fallback olarak HTTP poll
  const unreadCount = ws.unreadCount;

  // Eğer WS bağlı değilse veya başarısız olduysa fallback poll
  React.useEffect(() => {
    if (ws.connected) return; // WS bağlıysa poll yapma
    const loadUnread = async () => {
      try {
        const res = await axios.get("/notifications/unread-count");
        ws.setUnreadCount(res.data.count);
      } catch {}
    };
    loadUnread();
    const pollInterval = ws.wsStatus === "failed" ? 15000 : 60000; // WS başarısız ise daha sık poll
    const interval = setInterval(loadUnread, pollInterval);
    return () => clearInterval(interval);
  }, [ws.connected, ws.wsStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-brand">
          <div className="shell-brand-icon">🏨</div>
          CapX Platform
        </div>
        <div className="shell-right">
          <button className="theme-toggle" onClick={toggle} title={dark ? "Açık Mod" : "Koyu Mod"}>
            {dark ? "☀️" : "🌙"}
          </button>
          <span className={`ws-indicator ${ws.connected ? "ws-online" : ws.wsStatus === "connecting" ? "ws-connecting" : ws.wsStatus === "failed" ? "ws-failed" : "ws-offline"}`} title={ws.connected ? "Gerçek zamanlı bağlantı aktif" : ws.wsStatus === "connecting" ? "Bağlanıyor..." : ws.wsStatus === "failed" ? "Bağlantı kurulamadı (HTTP polling aktif)" : "Bağlantı yok"}>
            {ws.connected ? "🟢" : ws.wsStatus === "connecting" ? "🟡" : "🔴"}
          </span>
          <Link to="/notifications" className="notification-bell" title="Bildirimler">
            🔔
            {unreadCount > 0 && <span className="notification-badge">{unreadCount > 9 ? "9+" : unreadCount}</span>}
          </Link>
          <span className="shell-user">{hotel?.name}</span>
          {hotel?.is_admin && (
            <span className="admin-badge">⚙️ Admin</span>
          )}
          <button className="btn-ghost btn-sm" onClick={logout} data-testid="logout-button">
            Çıkış
          </button>
        </div>
      </header>

      <div className="shell-main">
        <nav className="shell-nav">
          <div className="shell-nav-label">Ana Menü</div>
          <Link to="/dashboard" className={isActive("/dashboard")} data-testid="nav-dashboard">
            📊 Panel
          </Link>
          <Link to="/listings" className={isActive("/listings")} data-testid="nav-listings">
            🔍 Kapasiteler
          </Link>
          <Link to="/availability" className={isActive("/availability")} data-testid="nav-availability">
            🏠 Kendi Kapasitem
          </Link>
          <Link to="/inventory" className={isActive("/inventory")} data-testid="nav-inventory">
            📦 Envanter
          </Link>
          <Link to="/requests" className={isActive("/requests")} data-testid="nav-requests">
            📋 Talepler
          </Link>
          <Link to="/matches" className={isActive("/matches")} data-testid="nav-matches">
            🤝 Eşleşmeler
          </Link>
          <div className="shell-nav-divider" />
          <div className="shell-nav-label">Finans</div>
          <Link to="/payments" className={isActive("/payments")}>
            💳 Ödemeler
          </Link>
          <Link to="/invoices" className={isActive("/invoices")}>
            🧾 Faturalar
          </Link>
          <Link to="/subscription" className={isActive("/subscription")}>
            ⭐ Abonelik
          </Link>
          <div className="shell-nav-divider" />
          <div className="shell-nav-label">Hesap</div>
          <Link to="/pricing" className={isActive("/pricing")}>
            💰 Fiyatlama
          </Link>
          <Link to="/reports" className={isActive("/reports")}>
            📈 Raporlar
          </Link>
          <Link to="/profile" className={isActive("/profile")}>
            👤 Profilim
          </Link>
          {hotel?.is_admin && (
            <>
              <div className="shell-nav-divider" />
              <div className="shell-nav-label">Yönetim</div>
              <Link to="/admin" className={isActive("/admin")}>
                ⚙️ Admin Panel
              </Link>
              <Link to="/performance" className={isActive("/performance")}>
                🚀 Performans
              </Link>
            </>
          )}
        </nav>
        <main className="shell-content">{children}</main>
      </div>
    </div>
  );
};

export default Layout;
