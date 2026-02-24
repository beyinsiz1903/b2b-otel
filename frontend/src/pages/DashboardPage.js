import React from "react";
import { useNavigate } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";

const DashboardPage = () => {
  const { hotel } = useAuth();
  const [stats, setStats] = React.useState(null);
  const navigate = useNavigate();

  React.useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get("/stats");
        setStats(res.data);
      } catch {
        setStats({});
      }
    };
    load();
  }, []);

  const pendingCount = stats?.pending_incoming ?? 0;

  return (
    <Layout>
      <div className="page-header">
        <h1 className="page-title" style={{ margin: 0 }}>
          Genel Bakış
        </h1>
        <span style={{ fontSize: "0.85rem", color: "#6b7c93" }}>
          Hoş geldiniz, <strong>{hotel?.name}</strong>
        </span>
      </div>

      {pendingCount > 0 && (
        <div className="warning-banner" style={{ cursor: "pointer" }} onClick={() => navigate("/requests")}>
          ⚠️ <strong>{pendingCount} bekleyen gelen talebiniz var.</strong> Taleplere gitmek için tıklayın →
        </div>
      )}

      <div className="cards-row" style={{ marginBottom: "2rem" }}>
        <div className="kpi-card kpi-green" data-testid="kpi-outgoing">
          <span>Gönderilen Talepler</span>
          <strong>{stats?.total_outgoing_requests ?? "-"}</strong>
          <div className="kpi-sub">Kabul: {stats?.accepted_outgoing ?? 0}</div>
        </div>
        <div className="kpi-card kpi-blue" data-testid="kpi-incoming">
          <span>Gelen Talepler</span>
          <strong>{stats?.total_incoming_requests ?? "-"}</strong>
          <div className="kpi-sub">Bekleyen: {stats?.pending_incoming ?? 0}</div>
        </div>
        <div className="kpi-card kpi-orange" data-testid="kpi-matches">
          <span>Toplam Eşleşme</span>
          <strong>{stats?.total_matches ?? "-"}</strong>
          <div className="kpi-sub">Toplam: {stats?.total_fees ? `${stats.total_fees} TL` : "0 TL"}</div>
        </div>
        <div className="kpi-card kpi-red" data-testid="kpi-monthly-fee">
          <span>Bu Ay</span>
          <strong>{stats?.this_month_matches ?? "-"}</strong>
          <div className="kpi-sub">{stats?.this_month_fees ? `${stats.this_month_fees} TL` : "0 TL"} bedel</div>
        </div>
      </div>

      <div className="cards-row">
        <div className="kpi-card">
          <span>Aktif İlanlarım</span>
          <strong>{stats?.active_listings ?? "-"}</strong>
          <div className="kpi-sub">Süresi Geçmiş: {stats?.expired_listings ?? 0}</div>
        </div>
        <div className="kpi-card">
          <span>Gönderilen Kabul Oranı</span>
          <strong style={{ fontSize: "1.4rem" }}>{stats?.acceptance_rate_outgoing ?? 0}%</strong>
          <div className="kpi-sub">Gönderilen taleplerden</div>
        </div>
        <div className="kpi-card">
          <span>Gelen Kabul Oranı</span>
          <strong style={{ fontSize: "1.4rem" }}>{stats?.acceptance_rate_incoming ?? 0}%</strong>
          <div className="kpi-sub">Gelen taleplerden</div>
        </div>
      </div>

      <div style={{ marginTop: "2rem", display: "flex", gap: "1rem", flexWrap: "wrap" }}>
        <button className="btn-primary" onClick={() => navigate("/availability")}>
          + Yeni Kapasite İlanı
        </button>
        <button className="btn-secondary" onClick={() => navigate("/listings")}>
          🔍 İlanları Gözat
        </button>
        <button className="btn-secondary" onClick={() => navigate("/reports")}>
          📈 Raporlar
        </button>
      </div>
    </Layout>
  );
};

export default DashboardPage;
