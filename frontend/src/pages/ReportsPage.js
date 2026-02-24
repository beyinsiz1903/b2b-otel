import React from "react";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";

const ReportsPage = () => {
  const [stats, setStats] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [tab, setTab] = React.useState("overview");
  const [marketTrends, setMarketTrends] = React.useState(null);
  const [perfScores, setPerfScores] = React.useState(null);
  const [revenue, setRevenue] = React.useState(null);
  const [reqStats, setReqStats] = React.useState(null);
  const [reqPeriod, setReqPeriod] = React.useState(30);
  const [crossRegion, setCrossRegion] = React.useState(null);

  React.useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get("/stats");
        setStats(res.data);
      } catch { setStats(null); }
      finally { setLoading(false); }
    };
    load();
  }, []);

  React.useEffect(() => {
    if (tab === "market" && !marketTrends) {
      axios.get("/stats/market-trends").then((r) => setMarketTrends(r.data)).catch(() => {});
    }
    if (tab === "performance" && !perfScores) {
      axios.get("/stats/performance-scores").then((r) => setPerfScores(r.data)).catch(() => {});
    }
    if (tab === "revenue" && !revenue) {
      axios.get("/reports/revenue").then((r) => setRevenue(r.data)).catch(() => {});
    }
    if (tab === "cross_region" && !crossRegion) {
      axios.get("/stats/cross-region").then((r) => setCrossRegion(r.data)).catch(() => {});
    }
  }, [tab, marketTrends, perfScores, revenue, crossRegion]);

  // Dönem değişince talep istatistiklerini yeniden yükle
  React.useEffect(() => {
    if (tab === "requests") {
      setReqStats(null);
      axios.get(`/stats/requests?period_days=${reqPeriod}`).then((r) => setReqStats(r.data)).catch(() => {});
    }
  }, [tab, reqPeriod]);

  if (loading) return <Layout><div className="page-center" style={{ height: 300 }}><span className="loading-spin" /></div></Layout>;
  if (!stats) return <Layout><div className="error">İstatistikler yüklenemedi.</div></Layout>;

  const allMonthKeys = Object.keys({ ...stats.monthly_matches, ...stats.monthly_fees }).sort();
  const last6 = allMonthKeys.slice(-6);
  const maxMatches = Math.max(...last6.map((k) => stats.monthly_matches[k] || 0), 1);
  const regions = Object.entries(stats.region_counts || {});
  const maxRegion = Math.max(...regions.map(([, v]) => v), 1);

  const tabs = [
    { id: "overview", label: "📊 Genel Bakış" },
    { id: "requests", label: "📋 Talep İstatistikleri" },
    { id: "market", label: "🌍 Pazar Trendleri" },
    { id: "performance", label: "🏆 Performans" },
    { id: "revenue", label: "💰 Gelir" },
    { id: "cross_region", label: "🔄 Bölgeler Arası" },
  ];

  // Talep İstatistikleri helpers
  const incomingTotal = reqStats?.incoming?.total || 0;
  const incomingAccepted = reqStats?.incoming?.by_status?.accepted || 0;
  const incomingRejected = reqStats?.incoming?.by_status?.rejected || 0;
  const incomingPending = reqStats?.incoming?.by_status?.pending || 0;
  const incomingAlt = reqStats?.incoming?.by_status?.alternative_offered || 0;
  const incomingCancelled = reqStats?.incoming?.by_status?.cancelled || 0;
  const incomingMissed = incomingRejected + incomingCancelled;

  return (
    <Layout>
      <h1 className="page-title">📈 Raporlar & Analitik</h1>
      <div className="tab-bar" style={{ marginBottom: "1.5rem", flexWrap: "wrap" }}>
        {tabs.map((t) => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

      {/* ═══════ GENEL BAKIŞ ═══════ */}
      {tab === "overview" && (
        <>
          <div className="cards-row" style={{ marginBottom: "2rem" }}>
            <div className="kpi-card kpi-green"><span>Toplam Eşleşme</span><strong>{stats.total_matches}</strong></div>
            <div className="kpi-card kpi-blue"><span>Toplam Hizmet Bedeli</span><strong style={{ fontSize: "1.3rem" }}>{stats.total_fees?.toLocaleString("tr-TR")} TL</strong></div>
            <div className="kpi-card kpi-orange"><span>Gönderilen Kabul %</span><strong>{stats.acceptance_rate_outgoing}%</strong></div>
            <div className="kpi-card"><span>Gelen Kabul %</span><strong>{stats.acceptance_rate_incoming}%</strong></div>
          </div>
          <div className="reports-grid">
            <div className="report-card">
              <h3>📅 Aylık Eşleşmeler</h3>
              {last6.length === 0 ? <div className="text-muted text-sm">Henüz veri yok</div> : (
                <div className="bar-chart">
                  {last6.map((month) => {
                    const count = stats.monthly_matches[month] || 0;
                    const pct = Math.max((count / maxMatches) * 100, 2);
                    return (<div key={month} className="bar-row"><div className="bar-label">{month.slice(5)}/{month.slice(2, 4)}</div><div className="bar-track"><div className="bar-fill" style={{ width: `${pct}%` }}>{count > 0 && <span className="bar-value">{count}</span>}</div></div></div>);
                  })}
                </div>
              )}
            </div>
            <div className="report-card">
              <h3>📍 Bölgesel Eşleşmeler</h3>
              {regions.length === 0 ? <div className="text-muted text-sm">Henüz veri yok</div> : (
                <div className="bar-chart">
                  {regions.map(([region, count]) => {
                    const pct = Math.max((count / maxRegion) * 100, 2);
                    return (<div key={region} className="bar-row"><div className="bar-label" style={{ width: 80 }}>{region}</div><div className="bar-track"><div className="bar-fill" style={{ width: `${pct}%`, background: "linear-gradient(90deg, #1d4ed8, #60a5fa)" }}><span className="bar-value">{count}</span></div></div></div>);
                  })}
                </div>
              )}
            </div>
            <div className="report-card">
              <h3>🏠 İlan Durumu</h3>
              <div className="stats-list">
                <div className="stats-row"><span className="stats-row-label">Aktif İlanlar</span><span className="stats-row-value text-green">{stats.active_listings}</span></div>
                <div className="stats-row"><span className="stats-row-label">Süresi Geçmiş</span><span className="stats-row-value text-muted">{stats.expired_listings}</span></div>
                <div className="stats-row"><span className="stats-row-label">Bu Ay Eşleşme</span><span className="stats-row-value">{stats.this_month_matches}</span></div>
                <div className="stats-row"><span className="stats-row-label">Bu Ay Bedel</span><span className="stats-row-value">{stats.this_month_fees?.toLocaleString("tr-TR")} TL</span></div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ═══════ TALEP İSTATİSTİKLERİ (Dönem bazlı) ═══════ */}
      {tab === "requests" && (
        <div>
          {/* Dönem Seçici */}
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
            {[
              { val: 7, label: "Son 7 gün" },
              { val: 30, label: "Son 30 gün" },
              { val: 90, label: "Son 90 gün" },
              { val: 180, label: "Son 6 ay" },
              { val: 365, label: "Son 1 yıl" },
            ].map((p) => (
              <button key={p.val} onClick={() => setReqPeriod(p.val)}
                style={{
                  padding: "0.5rem 1rem", borderRadius: "0.5rem", border: "1px solid #d1d5db",
                  background: reqPeriod === p.val ? "#1a3a2a" : "white",
                  color: reqPeriod === p.val ? "white" : "#374151",
                  fontWeight: reqPeriod === p.val ? 700 : 400,
                  cursor: "pointer", fontSize: "0.85rem",
                }}>{p.label}</button>
            ))}
          </div>

          {reqStats ? (
            <>
              {/* KPI Özet Kartları */}
              <div className="cards-row" style={{ marginBottom: "1.5rem" }}>
                <div className="kpi-card kpi-blue"><span>Alınan Talepler</span><strong>{incomingTotal}</strong></div>
                <div className="kpi-card kpi-green"><span>Karşılanan</span><strong>{incomingAccepted}</strong></div>
                <div className="kpi-card kpi-red"><span>Kaçırılan</span><strong>{incomingMissed}</strong></div>
                <div className="kpi-card kpi-orange"><span>Bekleyen</span><strong>{incomingPending + incomingAlt}</strong></div>
              </div>

              <div className="reports-grid">
                <div className="report-card">
                  <h3>📥 Gelen Talepler (Son {reqStats.period_days} gün)</h3>
                  <div className="stats-list">
                    <div className="stats-row"><span className="stats-row-label">Toplam</span><span className="stats-row-value">{reqStats.incoming?.total}</span></div>
                    {Object.entries(reqStats.incoming?.by_status || {}).map(([s, c]) => (
                      <div key={s} className="stats-row"><span className="stats-row-label">{statusLabel(s)}</span><span className="stats-row-value">{c}</span></div>
                    ))}
                  </div>
                  <div style={{ marginTop: "1rem" }}>
                    <div style={{ fontSize: "0.85rem", color: "#6b7c93" }}>Kabul Oranı</div>
                    <div className="rate-indicator"><div className="rate-bar-outer"><div className="rate-bar-inner" style={{ width: `${reqStats.acceptance_rate}%` }} /></div><span style={{ fontWeight: 700 }}>{reqStats.acceptance_rate}%</span></div>
                  </div>
                  <div style={{ marginTop: "0.5rem" }}>
                    <div style={{ fontSize: "0.85rem", color: "#6b7c93" }}>Kaçırma Oranı</div>
                    <div className="rate-indicator"><div className="rate-bar-outer"><div className="rate-bar-inner" style={{ width: `${reqStats.missed_rate}%`, background: "#ef4444" }} /></div><span style={{ fontWeight: 700, color: "#ef4444" }}>{reqStats.missed_rate}%</span></div>
                  </div>
                </div>

                <div className="report-card">
                  <h3>📤 Gönderilen Talepler</h3>
                  <div className="stats-list">
                    <div className="stats-row"><span className="stats-row-label">Toplam</span><span className="stats-row-value">{reqStats.outgoing?.total}</span></div>
                    {Object.entries(reqStats.outgoing?.by_status || {}).map(([s, c]) => (
                      <div key={s} className="stats-row"><span className="stats-row-label">{statusLabel(s)}</span><span className="stats-row-value">{c}</span></div>
                    ))}
                  </div>
                </div>

                {/* Günlük Trend Grafiği */}
                <div className="report-card" style={{ gridColumn: "1 / -1" }}>
                  <h3>📈 Günlük Gelen Talep Trendi</h3>
                  {Object.keys(reqStats.incoming?.daily || {}).length === 0 ? (
                    <div className="text-muted text-sm">Bu dönemde gelen talep yok</div>
                  ) : (
                    <div style={{ display: "flex", gap: "2px", alignItems: "flex-end", height: 120, padding: "0.5rem 0" }}>
                      {(() => {
                        const dailyData = reqStats.incoming?.daily || {};
                        const sortedDays = Object.keys(dailyData).sort();
                        const maxDaily = Math.max(...Object.values(dailyData), 1);
                        return sortedDays.map((day) => {
                          const count = dailyData[day] || 0;
                          const pct = Math.max((count / maxDaily) * 100, 5);
                          return (
                            <div key={day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end" }}>
                              <div style={{ fontSize: "0.6rem", fontWeight: 600, color: "#1a3a2a", marginBottom: 2 }}>{count}</div>
                              <div style={{ width: "100%", maxWidth: 30, height: `${pct}%`, background: "linear-gradient(180deg, #2e6b57, #4ade80)", borderRadius: "3px 3px 0 0", minHeight: 4 }} title={`${day}: ${count}`} />
                              <div style={{ fontSize: "0.55rem", color: "#6b7c93", marginTop: 2, whiteSpace: "nowrap", transform: "rotate(-45deg)", transformOrigin: "top left", width: 0 }}>{day.slice(5)}</div>
                            </div>
                          );
                        });
                      })()}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : <div className="page-center"><span className="loading-spin" /></div>}
        </div>
      )}

      {/* ═══════ PAZAR TRENDLERİ (Bölge bazlı arz/talep) ═══════ */}
      {tab === "market" && (
        <div>
          <h2 style={{ marginBottom: "1rem" }}>🌍 Pazar Trendleri - Bölgesel Arz/Talep Dengesi</h2>
          {marketTrends ? (
            <>
              {/* Özet Bar */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "0.75rem", marginBottom: "1.5rem" }}>
                {Object.entries(marketTrends).map(([key, data]) => {
                  const total = data.supply + data.demand;
                  const supplyPct = total > 0 ? Math.round((data.supply / total) * 100) : 50;
                  return (
                    <div key={key} style={{ background: "white", borderRadius: "0.75rem", padding: "0.75rem", boxShadow: "0 1px 4px rgba(0,0,0,0.08)" }}>
                      <div style={{ fontWeight: 700, fontSize: "0.85rem", marginBottom: "0.5rem" }}>{data.label}</div>
                      <div style={{ display: "flex", borderRadius: 4, overflow: "hidden", height: 8, marginBottom: "0.4rem" }}>
                        <div style={{ width: `${supplyPct}%`, background: "#10b981" }} title={`Arz: ${data.supply}`} />
                        <div style={{ width: `${100 - supplyPct}%`, background: "#ef4444" }} title={`Talep: ${data.demand}`} />
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", color: "#6b7c93" }}>
                        <span>Arz: {data.supply}</span><span>Talep: {data.demand}</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Detay Kartları */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
                {Object.entries(marketTrends).map(([key, data]) => (
                  <div key={key} className="card" style={{ borderLeft: `4px solid ${data.balance === "dengeli" ? "#10b981" : data.balance === "talep_fazla" ? "#ef4444" : "#3b82f6"}`, position: "relative" }}>
                    <div style={{ position: "absolute", top: 12, right: 12, padding: "2px 10px", borderRadius: 20, fontSize: "0.72rem", fontWeight: 600, background: data.balance === "dengeli" ? "#ecfdf5" : data.balance === "talep_fazla" ? "#fef2f2" : "#eff6ff", color: data.balance === "dengeli" ? "#059669" : data.balance === "talep_fazla" ? "#dc2626" : "#2563eb" }}>
                      {data.balance === "dengeli" ? "⚖️ Dengeli" : data.balance === "talep_fazla" ? "📈 Talep Fazla" : "📉 Arz Fazla"}
                    </div>
                    <h3>{data.label}</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem", margin: "1rem 0" }}>
                      <div style={{ textAlign: "center", padding: "0.5rem", background: "#f0fdf4", borderRadius: "0.5rem" }}>
                        <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#10b981" }}>{data.supply}</div>
                        <div style={{ fontSize: "0.7rem", color: "#6b7c93" }}>Arz</div>
                      </div>
                      <div style={{ textAlign: "center", padding: "0.5rem", background: "#fef2f2", borderRadius: "0.5rem" }}>
                        <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#ef4444" }}>{data.demand}</div>
                        <div style={{ fontSize: "0.7rem", color: "#6b7c93" }}>Talep</div>
                      </div>
                      <div style={{ textAlign: "center", padding: "0.5rem", background: "#eff6ff", borderRadius: "0.5rem" }}>
                        <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#3b82f6" }}>{data.matches}</div>
                        <div style={{ fontSize: "0.7rem", color: "#6b7c93" }}>Eşleşme</div>
                      </div>
                    </div>
                    <div className="stats-list" style={{ fontSize: "0.85rem" }}>
                      <div className="stats-row"><span className="stats-row-label">Ort. Fiyat</span><span className="stats-row-value">₺{data.avg_price?.toLocaleString("tr-TR")}</span></div>
                      <div className="stats-row"><span className="stats-row-label">Eşleşme Ücreti</span><span className="stats-row-value">₺{data.match_fee}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : <div className="page-center"><span className="loading-spin" /></div>}
        </div>
      )}

      {/* ═══════ PERFORMANS SKORLARI ═══════ */}
      {tab === "performance" && (
        <div>
          {perfScores ? (
            <div className="reports-grid">
              <div className="report-card" style={{ gridColumn: "1 / -1" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "2rem", flexWrap: "wrap" }}>
                  {/* Skor dairesi */}
                  <div style={{ textAlign: "center", minWidth: "140px" }}>
                    <div style={{ width: 120, height: 120, borderRadius: "50%", border: `6px solid ${perfScores.grade === "A" ? "#10b981" : perfScores.grade === "B" ? "#3b82f6" : perfScores.grade === "C" ? "#f59e0b" : "#ef4444"}`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", margin: "0 auto" }}>
                      <div style={{ fontSize: "2.5rem", fontWeight: 800, color: perfScores.grade === "A" ? "#10b981" : perfScores.grade === "B" ? "#3b82f6" : perfScores.grade === "C" ? "#f59e0b" : "#ef4444", lineHeight: 1 }}>{perfScores.grade}</div>
                      <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "#374151" }}>{perfScores.score}/100</div>
                    </div>
                    <div style={{ color: "#6b7c93", fontSize: "0.8rem", marginTop: "0.5rem" }}>Son {perfScores.period_days} gün</div>
                  </div>

                  {/* Metrikler */}
                  <div style={{ flex: 1 }}>
                    <h3>🏆 Performans Skorları</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem", marginTop: "1rem" }}>
                      {/* Onay Oranı */}
                      <div style={{ background: "#f0fdf4", padding: "1rem", borderRadius: "0.75rem" }}>
                        <div style={{ fontSize: "0.8rem", color: "#6b7c93", marginBottom: "0.25rem" }}>Onay Oranı</div>
                        <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#10b981" }}>{perfScores.approval_rate}%</div>
                        <div style={{ height: 6, borderRadius: 3, background: "#e5e7eb", marginTop: "0.5rem" }}><div style={{ height: "100%", borderRadius: 3, background: "#10b981", width: `${perfScores.approval_rate}%` }} /></div>
                      </div>
                      {/* İptal Oranı */}
                      <div style={{ background: "#fef2f2", padding: "1rem", borderRadius: "0.75rem" }}>
                        <div style={{ fontSize: "0.8rem", color: "#6b7c93", marginBottom: "0.25rem" }}>İptal Oranı</div>
                        <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#ef4444" }}>{perfScores.cancellation_rate}%</div>
                        <div style={{ height: 6, borderRadius: 3, background: "#e5e7eb", marginTop: "0.5rem" }}><div style={{ height: "100%", borderRadius: 3, background: "#ef4444", width: `${Math.min(perfScores.cancellation_rate, 100)}%` }} /></div>
                      </div>
                      {/* Cevap Süresi */}
                      <div style={{ background: "#eff6ff", padding: "1rem", borderRadius: "0.75rem" }}>
                        <div style={{ fontSize: "0.8rem", color: "#6b7c93", marginBottom: "0.25rem" }}>Ort. Cevap Süresi</div>
                        <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#3b82f6" }}>{perfScores.avg_response_hours}h</div>
                        <div style={{ fontSize: "0.75rem", color: "#6b7c93", marginTop: "0.5rem" }}>{perfScores.avg_response_hours < 2 ? "⚡ Çok Hızlı" : perfScores.avg_response_hours < 6 ? "✅ İyi" : perfScores.avg_response_hours < 24 ? "⚠️ Geliştirilebilir" : "🔴 Yavaş"}</div>
                      </div>
                      {/* Eşleşme */}
                      <div style={{ background: "#fefce8", padding: "1rem", borderRadius: "0.75rem" }}>
                        <div style={{ fontSize: "0.8rem", color: "#6b7c93", marginBottom: "0.25rem" }}>Eşleşme Sayısı</div>
                        <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#a16207" }}>{perfScores.match_count}</div>
                        <div style={{ fontSize: "0.75rem", color: "#6b7c93", marginTop: "0.5rem" }}>{perfScores.period_days} gün içinde</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="report-card">
                <h3>📋 Talep Kırılımı</h3>
                <div className="stats-list">
                  <div className="stats-row"><span className="stats-row-label">Toplam Gelen</span><span className="stats-row-value">{perfScores.total_incoming_requests}</span></div>
                  <div className="stats-row"><span className="stats-row-label">Kabul</span><span className="stats-row-value" style={{ color: "#10b981" }}>{perfScores.accepted}</span></div>
                  <div className="stats-row"><span className="stats-row-label">Red</span><span className="stats-row-value" style={{ color: "#ef4444" }}>{perfScores.rejected}</span></div>
                  <div className="stats-row"><span className="stats-row-label">Alternatif</span><span className="stats-row-value" style={{ color: "#3b82f6" }}>{perfScores.alternative_offered}</span></div>
                  <div className="stats-row"><span className="stats-row-label">İptal</span><span className="stats-row-value" style={{ color: "#ef4444" }}>{perfScores.cancelled}</span></div>
                  <div className="stats-row"><span className="stats-row-label">Bekleyen</span><span className="stats-row-value" style={{ color: "#f59e0b" }}>{perfScores.pending}</span></div>
                </div>
                {/* Mini pie-like visual */}
                {perfScores.total_incoming_requests > 0 && (
                  <div style={{ display: "flex", borderRadius: 4, overflow: "hidden", height: 12, marginTop: "1rem" }}>
                    {perfScores.accepted > 0 && <div style={{ flex: perfScores.accepted, background: "#10b981" }} title={`Kabul: ${perfScores.accepted}`} />}
                    {perfScores.alternative_offered > 0 && <div style={{ flex: perfScores.alternative_offered, background: "#3b82f6" }} title={`Alternatif: ${perfScores.alternative_offered}`} />}
                    {perfScores.pending > 0 && <div style={{ flex: perfScores.pending, background: "#f59e0b" }} title={`Bekleyen: ${perfScores.pending}`} />}
                    {perfScores.rejected > 0 && <div style={{ flex: perfScores.rejected, background: "#ef4444" }} title={`Red: ${perfScores.rejected}`} />}
                    {perfScores.cancelled > 0 && <div style={{ flex: perfScores.cancelled, background: "#991b1b" }} title={`İptal: ${perfScores.cancelled}`} />}
                  </div>
                )}
              </div>
            </div>
          ) : <div className="page-center"><span className="loading-spin" /></div>}
        </div>
      )}

      {/* ═══════ GELİR ═══════ */}
      {tab === "revenue" && (
        <div>
          {revenue ? (
            <div className="reports-grid">
              <div className="report-card" style={{ gridColumn: "1 / -1" }}>
                <div className="cards-row">
                  <div className="kpi-card kpi-green"><span>Toplam Eşleşme</span><strong>{revenue.total_matches}</strong></div>
                  <div className="kpi-card kpi-blue"><span>Toplam Ödeme</span><strong>₺{revenue.total_payments?.toLocaleString("tr-TR")}</strong></div>
                </div>
              </div>
              <div className="report-card">
                <h3>📅 Aylık Gelir</h3>
                {Object.keys(revenue.monthly || {}).length === 0 ? <div className="text-muted">Henüz veri yok</div> : (
                  <div className="stats-list">
                    {Object.entries(revenue.monthly).sort().map(([month, data]) => (
                      <div key={month} className="stats-row"><span className="stats-row-label">{month}</span><span className="stats-row-value">₺{data.revenue?.toLocaleString("tr-TR")} ({data.matches} eşleşme)</span></div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : <div className="page-center"><span className="loading-spin" /></div>}
        </div>
      )}

      {/* ═══════ BÖLGELER ARASI KAPASİTE PAYLAŞIMI ═══════ */}
      {tab === "cross_region" && (
        <div>
          <h2 style={{ marginBottom: "1rem" }}>🔄 Bölgeler Arası Kapasite Paylaşımı</h2>
          {crossRegion ? (
            <div className="reports-grid">
              {/* KPI */}
              <div className="report-card" style={{ gridColumn: "1 / -1" }}>
                <div className="cards-row">
                  <div className="kpi-card kpi-blue"><span>Cross-Region İlan</span><strong>{crossRegion.total_cross_region_listings}</strong></div>
                  <div className="kpi-card kpi-green"><span>Cross-Region Eşleşme</span><strong>{crossRegion.total_cross_region_matches}</strong></div>
                  <div className="kpi-card kpi-orange"><span>Aktif Bölge</span><strong>{crossRegion.regions?.length}</strong></div>
                </div>
              </div>

              {/* Bölge dağılımı */}
              <div className="report-card">
                <h3>📊 Bölge Bazlı Cross-Region İlanlar</h3>
                {Object.keys(crossRegion.region_breakdown || {}).length === 0 ? (
                  <div className="text-muted text-sm" style={{ padding: "1rem 0" }}>
                    Henüz bölgeler arası ilan yok. İlan oluştururken "🌍 Bölgeler arası paylaşıma aç" seçeneğini işaretleyin.
                  </div>
                ) : (
                  <div className="bar-chart">
                    {Object.entries(crossRegion.region_breakdown).map(([region, data]) => {
                      const maxListings = Math.max(...Object.values(crossRegion.region_breakdown).map(d => d.listings), 1);
                      const pct = Math.max((data.listings / maxListings) * 100, 5);
                      return (
                        <div key={region} className="bar-row">
                          <div className="bar-label" style={{ width: 80 }}>{region}</div>
                          <div className="bar-track">
                            <div className="bar-fill" style={{ width: `${pct}%`, background: "linear-gradient(90deg, #6366f1, #a78bfa)" }}>
                              <span className="bar-value">{data.listings} ilan · {data.total_pax} pax</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Bölge çiftleri */}
              <div className="report-card">
                <h3>🔗 Bölge Çiftleri Eşleşme</h3>
                {Object.keys(crossRegion.region_pairs || {}).length === 0 ? (
                  <div className="text-muted text-sm" style={{ padding: "1rem 0" }}>
                    Henüz bölgeler arası eşleşme yok. Farklı bölgelerdeki oteller arasındaki eşleşmeler burada görüntülenecek.
                  </div>
                ) : (
                  <div className="stats-list">
                    {Object.entries(crossRegion.region_pairs).sort((a, b) => b[1] - a[1]).map(([pair, count]) => (
                      <div key={pair} className="stats-row">
                        <span className="stats-row-label">{pair}</span>
                        <span className="stats-row-value">{count} eşleşme</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Bölge Ağı Haritası */}
              <div className="report-card" style={{ gridColumn: "1 / -1" }}>
                <h3>🗺️ Bölge Ağı</h3>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", justifyContent: "center", padding: "1.5rem 0" }}>
                  {(crossRegion.regions || []).map((region) => {
                    const data = crossRegion.region_breakdown?.[region];
                    const hasListings = data && data.listings > 0;
                    return (
                      <div key={region} style={{
                        padding: "1rem 1.5rem", borderRadius: "1rem",
                        background: hasListings ? "linear-gradient(135deg, #1d4ed8, #3b82f6)" : "#f3f4f6",
                        color: hasListings ? "white" : "#6b7c93",
                        fontWeight: 600, fontSize: "0.9rem",
                        boxShadow: hasListings ? "0 4px 12px rgba(29,78,216,0.3)" : "none",
                        minWidth: 100, textAlign: "center",
                      }}>
                        <div>{region}</div>
                        {hasListings && <div style={{ fontSize: "0.7rem", opacity: 0.9, marginTop: 2 }}>{data.listings} ilan</div>}
                      </div>
                    );
                  })}
                </div>
                <div style={{ textAlign: "center", fontSize: "0.8rem", color: "#6b7c93", marginTop: "0.5rem" }}>
                  Mavi: Aktif cross-region ilanı var · Gri: Henüz cross-region ilanı yok
                </div>
              </div>
            </div>
          ) : <div className="page-center"><span className="loading-spin" /></div>}
        </div>
      )}
    </Layout>
  );
};

export default ReportsPage;
