import React from "react";
import { useNavigate } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Modal from "@/components/Modal";

const AdminPage = () => {
  const { hotel } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = React.useState("pending");
  const [overview, setOverview] = React.useState(null);
  const [pending, setPending] = React.useState([]);
  const [hotels, setHotels] = React.useState([]);
  const [matches, setMatches] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [rejectModal, setRejectModal] = React.useState(null);
  const [rejectReason, setRejectReason] = React.useState("");
  const [docModal, setDocModal] = React.useState(null);
  const [actionMsg, setActionMsg] = React.useState("");
  const [adminRevenue, setAdminRevenue] = React.useState(null);
  const [regionPricing, setRegionPricing] = React.useState([]);
  const [regionStats, setRegionStats] = React.useState(null);
  const [activityLogs, setActivityLogs] = React.useState([]);
  const [logLoading, setLogLoading] = React.useState(false);

  React.useEffect(() => {
    if (!hotel?.is_admin) navigate("/dashboard");
  }, [hotel, navigate]);

  React.useEffect(() => {
    if (tab === "pending") loadPending();
    if (tab === "overview") loadOverview();
    if (tab === "hotels") loadHotels();
    if (tab === "matches") loadAdminMatches();
    if (tab === "revenue") loadAdminRevenue();
    if (tab === "regions") loadRegionData();
  }, [tab]);

  const loadPending = async () => {
    setLoading(true);
    try {
      const res = await axios.get("/admin/hotels?status_filter=pending_review");
      setPending(res.data);
    } catch { setPending([]); } finally { setLoading(false); }
  };

  const loadOverview = async () => {
    setLoading(true);
    try { const res = await axios.get("/admin/overview"); setOverview(res.data); }
    catch { setOverview(null); } finally { setLoading(false); }
  };

  const loadHotels = async () => {
    setLoading(true);
    try { const res = await axios.get("/admin/hotels"); setHotels(res.data); }
    catch { setHotels([]); } finally { setLoading(false); }
  };

  const loadAdminMatches = async () => {
    setLoading(true);
    try { const res = await axios.get("/admin/matches"); setMatches(res.data); }
    catch { setMatches([]); } finally { setLoading(false); }
  };

  const approveHotel = async (hotelId) => {
    try {
      const res = await axios.put(`/admin/hotels/${hotelId}/approve`);
      setActionMsg(`✅ ${res.data.message}`);
      await loadPending(); await loadHotels();
    } catch (err) { alert(err.response?.data?.detail || "İşlem başarısız."); }
  };

  const rejectHotel = async () => {
    if (!rejectModal) return;
    try {
      const res = await axios.put(`/admin/hotels/${rejectModal.id}/reject`, { reason: rejectReason });
      setActionMsg(`❌ ${res.data.message}`);
      setRejectModal(null); setRejectReason("");
      await loadPending(); await loadHotels();
    } catch (err) { alert(err.response?.data?.detail || "İşlem başarısız."); }
  };

  const toggleAdmin = async (hotelId) => {
    try { await axios.put(`/admin/hotels/${hotelId}/toggle-admin`); await loadHotels(); }
    catch (err) { alert(err.response?.data?.detail || "İşlem başarısız."); }
  };

  const updateFeeStatus = async (matchId, status) => {
    try { await axios.put(`/admin/matches/${matchId}/fee-status`, { fee_status: status }); await loadAdminMatches(); }
    catch (err) { alert(err.response?.data?.detail || "İşlem başarısız."); }
  };

  const loadAdminRevenue = async () => {
    setLoading(true);
    try { const res = await axios.get("/admin/revenue"); setAdminRevenue(res.data); }
    catch {} finally { setLoading(false); }
  };

  const loadRegionData = async () => {
    setLoading(true);
    try {
      const [pricing, stats] = await Promise.all([
        axios.get("/admin/region-pricing"),
        axios.get("/admin/region-stats"),
      ]);
      setRegionPricing(pricing.data);
      setRegionStats(stats.data);
    } catch {} finally { setLoading(false); }
  };

  const updateRegionFee = async (region, newFee) => {
    try {
      await axios.put(`/admin/region-pricing/${region}`, { match_fee: parseFloat(newFee) });
      setActionMsg(`✅ ${region} bölgesi ücreti güncellendi`);
      loadRegionData();
    } catch (err) { alert(err.response?.data?.detail || "Hata"); }
  };

  const approvalStatusChip = (s) => {
    if (s === "approved") return <span style={{ fontSize: "0.72rem", background: "#dcfce7", color: "#166534", borderRadius: "999px", padding: "0.15rem 0.6rem", fontWeight: 700 }}>✅ Onaylı</span>;
    if (s === "pending_review") return <span style={{ fontSize: "0.72rem", background: "#fef9c3", color: "#713f12", borderRadius: "999px", padding: "0.15rem 0.6rem", fontWeight: 700 }}>⏳ Bekliyor</span>;
    if (s === "rejected") return <span style={{ fontSize: "0.72rem", background: "#fee2e2", color: "#991b1b", borderRadius: "999px", padding: "0.15rem 0.6rem", fontWeight: 700 }}>❌ Reddedildi</span>;
    return null;
  };

  return (
    <Layout>
      <div className="flex items-center gap-2" style={{ marginBottom: "1.5rem" }}>
        <h1 className="page-title" style={{ margin: 0 }}>⚙️ Admin Paneli</h1>
        <span className="admin-badge">Platform Yöneticisi</span>
      </div>

      {actionMsg && (
        <div className="success mb-2" style={{ cursor: "pointer" }} onClick={() => setActionMsg("")}>
          {actionMsg} <span style={{ float: "right", opacity: 0.5 }}>✕</span>
        </div>
      )}

      <div className="admin-tabs">
        <div className={`admin-tab ${tab === "pending" ? "active" : ""}`} onClick={() => setTab("pending")} style={{ position: "relative" }}>
          📋 Üyelik Talepleri
          {pending.length > 0 && <span className="notif-dot" style={{ position: "absolute", top: 6, right: 4 }} />}
          {` (${pending.length})`}
        </div>
        <div className={`admin-tab ${tab === "overview" ? "active" : ""}`} onClick={() => setTab("overview")}>
          📊 Genel Bakış
        </div>
        <div className={`admin-tab ${tab === "hotels" ? "active" : ""}`} onClick={() => setTab("hotels")}>
          🏨 Tüm Oteller ({hotels.length})
        </div>
        <div className={`admin-tab ${tab === "matches" ? "active" : ""}`} onClick={() => setTab("matches")}>
          🤝 Eşleşmeler
        </div>
        <div className={`admin-tab ${tab === "revenue" ? "active" : ""}`} onClick={() => setTab("revenue")}>
          💰 Gelir
        </div>
        <div className={`admin-tab ${tab === "regions" ? "active" : ""}`} onClick={() => setTab("regions")}>
          🌍 Bölgeler
        </div>
        <div className={`admin-tab ${tab === "logs" ? "active" : ""}`} onClick={() => {
          setTab("logs");
          if (activityLogs.length === 0) {
            setLogLoading(true);
            axios.get("/admin/activity-logs?limit=50").then(r => setActivityLogs(r.data)).catch(() => {}).finally(() => setLogLoading(false));
          }
        }}>
          📜 Aktivite Log
        </div>
      </div>

      {loading ? (
        <div className="page-center" style={{ height: 200 }}><span className="loading-spin" /></div>
      ) : tab === "pending" ? (
        <>
          {pending.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">✅</div>
              <div className="empty-state-title">Bekleyen üyelik talebi yok</div>
              <div className="empty-state-sub">Tüm başvurular incelendi.</div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {pending.map((h) => (
                <div key={h.id} style={{ background: "#fff", borderRadius: "1rem", padding: "1.25rem", boxShadow: "0 2px 10px rgba(0,0,0,.05)", border: "1px solid #f0f4f8" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
                    <div style={{ flex: 1, minWidth: 250 }}>
                      <div style={{ fontWeight: 700, fontSize: "1rem", color: "#1a3a2a", marginBottom: "0.5rem" }}>{h.name}</div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.25rem 1rem", fontSize: "0.85rem", color: "#4a5568" }}>
                        <div>📧 {h.email}</div>
                        <div>📍 {h.region} · {h.concept}</div>
                        <div>📞 {h.phone}</div>
                        <div>🏠 {h.address}</div>
                        {h.contact_person && <div>👤 {h.contact_person}</div>}
                        <div style={{ color: "#9ca3af" }}>📅 {h.created_at ? new Date(h.created_at).toLocaleString("tr-TR") : "-"}</div>
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", alignItems: "flex-end" }}>
                      {h.documents && h.documents.length > 0 ? (
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => setDocModal({ hotel: h, docs: h.documents })}
                        >
                          📄 Belgeleri Gör ({h.documents.length})
                        </button>
                      ) : (
                        <span style={{ fontSize: "0.78rem", color: "#dc2626" }}>⚠️ Belge yüklenmemiş</span>
                      )}
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button className="btn-primary btn-sm" onClick={() => approveHotel(h.id)}>
                          ✅ Onayla
                        </button>
                        <button className="btn-danger btn-sm" onClick={() => { setRejectModal(h); setRejectReason(""); }}>
                          ❌ Reddet
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : tab === "overview" && overview ? (
        <>
          <div className="cards-row">
            <div className="kpi-card kpi-green">
              <span>Toplam Otel</span>
              <strong>{overview.total_hotels}</strong>
            </div>
            <div className="kpi-card">
              <span>Toplam İlan</span>
              <strong>{overview.total_listings}</strong>
            </div>
            <div className="kpi-card kpi-blue">
              <span>Toplam Talep</span>
              <strong>{overview.total_requests}</strong>
            </div>
            <div className="kpi-card kpi-orange">
              <span>Toplam Eşleşme</span>
              <strong>{overview.total_matches}</strong>
            </div>
          </div>
          <div className="cards-row">
            <div className="kpi-card">
              <span>Toplam Hizmet Bedeli</span>
              <strong style={{ fontSize: "1.2rem" }}>{overview.total_fees?.toLocaleString("tr-TR")} TL</strong>
            </div>
            <div className="kpi-card kpi-red">
              <span>Bekleyen Bedel</span>
              <strong style={{ fontSize: "1.2rem" }}>{overview.due_fees?.toLocaleString("tr-TR")} TL</strong>
            </div>
            <div className="kpi-card kpi-green">
              <span>Ödenen Bedel</span>
              <strong style={{ fontSize: "1.2rem" }}>{overview.paid_fees?.toLocaleString("tr-TR")} TL</strong>
            </div>
          </div>

          <div className="section-title">🕒 Son Aktiviteler</div>
          <div className="report-card">
            <div className="activity-log-list">
              {(overview.recent_activity || []).slice(0, 15).map((log) => (
                <div key={log.id} className="activity-log-item">
                  <div className="activity-log-dot" />
                  <div>
                    <span className="activity-log-action">{log.action}</span>{" "}
                    <span style={{ color: "#6b7c93" }}>→ {log.entity} · {log.entity_id?.slice(0, 8)}...</span>
                  </div>
                  <div className="activity-log-time">
                    {log.created_at ? new Date(log.created_at).toLocaleString("tr-TR") : "-"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : tab === "hotels" ? (
        <div className="matches-table-wrap">
          <table className="requests-table">
            <thead>
              <tr>
                <th>Otel Adı</th>
                <th>E-posta</th>
                <th>Bölge</th>
                <th>Durum</th>
                <th>İlan</th>
                <th>Eşleşme</th>
                <th>Kayıt Tarihi</th>
                <th>Admin</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {hotels.map((h) => (
                <tr key={h.id}>
                  <td style={{ fontWeight: 600 }}>{h.name}</td>
                  <td style={{ fontSize: "0.82rem", color: "#6b7c93" }}>{h.email}</td>
                  <td><span className="badge-region">{h.region}</span></td>
                  <td>{approvalStatusChip(h.approval_status)}</td>
                  <td>{h.listing_count}</td>
                  <td>{h.match_count}</td>
                  <td style={{ fontSize: "0.8rem", color: "#6b7c93" }}>
                    {h.created_at ? new Date(h.created_at).toLocaleDateString("tr-TR") : "-"}
                  </td>
                  <td>
                    {h.is_admin ? <span className="admin-badge">Admin</span> : <span className="text-muted">-</span>}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                      {h.approval_status !== "approved" && (
                        <button className="btn-sm btn-primary" onClick={() => approveHotel(h.id)}>✅ Onayla</button>
                      )}
                      {h.approval_status === "approved" && (
                        <button className="btn-sm btn-danger" onClick={() => { setRejectModal(h); setRejectReason(""); }}>❌ İptal</button>
                      )}
                      <button
                        className={`btn-sm ${h.is_admin ? "btn-danger" : "btn-secondary"}`}
                        onClick={() => toggleAdmin(h.id)}
                      >
                        {h.is_admin ? "Admin Kaldır" : "Admin Yap"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : tab === "matches" ? (
        <div className="matches-table-wrap">
          <table className="requests-table">
            <thead>
              <tr>
                <th>Referans</th>
                <th>Otel A</th>
                <th>Otel B</th>
                <th>Bedel (TL)</th>
                <th>Ödeme</th>
                <th>Tarih</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m) => (
                <tr key={m.id}>
                  <td style={{ fontWeight: 700, fontFamily: "monospace", color: "#2e6b57" }}>{m.reference_code}</td>
                  <td style={{ fontSize: "0.85rem" }}>{m.hotel_a_name}</td>
                  <td style={{ fontSize: "0.85rem" }}>{m.hotel_b_name}</td>
                  <td style={{ fontWeight: 600 }}>{m.fee_amount?.toLocaleString("tr-TR")}</td>
                  <td>
                    <select
                      value={m.fee_status}
                      onChange={(e) => updateFeeStatus(m.id, e.target.value)}
                      style={{ fontSize: "0.8rem", padding: "0.2rem 0.4rem", borderRadius: "0.4rem", border: "1px solid #e2e8f0" }}
                    >
                      <option value="due">Bekliyor</option>
                      <option value="paid">Ödendi</option>
                      <option value="waived">Silindi</option>
                    </select>
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "#6b7c93" }}>
                    {m.accepted_at ? new Date(m.accepted_at).toLocaleDateString("tr-TR") : "-"}
                  </td>
                  <td>-</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {/* Reddet Modal */}
      <Modal open={!!rejectModal} onClose={() => setRejectModal(null)} title="❌ Başvuruyu Reddet" size="sm"
        footer={
          <>
            <button className="btn-ghost" onClick={() => setRejectModal(null)}>İptal</button>
            <button className="btn-danger" onClick={rejectHotel}>Reddet</button>
          </>
        }
      >
        <div style={{ fontSize: "0.9rem", color: "#374151", marginBottom: "0.75rem" }}>
          <strong>{rejectModal?.name}</strong> adlı otelin başvurusu reddedilecek.
        </div>
        <label className="field">
          <span>Red Gerekçesi (opsiyonel — otele gösterilir)</span>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={3}
            placeholder="Örn: Belgeler eksik, işletme belgesi geçersiz..."
          />
        </label>
      </Modal>

      {/* Belge Görüntüleme Modal */}
      {docModal && (
        <Modal open={true} onClose={() => setDocModal(null)} title={`📄 ${docModal.hotel.name} — Belgeler`}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {docModal.docs.map((filename, i) => {
              const isImg = /\.(jpg|jpeg|png|webp)$/i.test(filename);
              const url = `${process.env.REACT_APP_BACKEND_URL}/api/files/docs/${filename}`;
              return (
                <div key={i} style={{ border: "1px solid #e2e8f0", borderRadius: "0.75rem", overflow: "hidden" }}>
                  {isImg ? (
                    <img src={url} alt={`Belge ${i + 1}`} style={{ width: "100%", maxHeight: 400, objectFit: "contain", background: "#f8fafc" }} />
                  ) : (
                    <div style={{ padding: "1.25rem", textAlign: "center" }}>
                      <div style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>📄</div>
                      <div style={{ fontSize: "0.85rem", color: "#6b7c93", marginBottom: "0.75rem" }}>{filename}</div>
                    </div>
                  )}
                  <div style={{ padding: "0.5rem", borderTop: "1px solid #f0f4f8", textAlign: "center" }}>
                    <a href={url} target="_blank" rel="noopener noreferrer" className="btn-secondary btn-sm">
                      🔗 Yeni Sekmede Aç
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        </Modal>
      )}

      {/* Revenue Tab */}
      {tab === "revenue" && !loading && (
        <div>
          {adminRevenue ? (
            <>
              <div className="cards-row" style={{ marginBottom: "1.5rem" }}>
                <div className="kpi-card kpi-green"><span>Toplam Gelir</span><strong>₺{adminRevenue.total_revenue?.toLocaleString("tr-TR")}</strong></div>
                <div className="kpi-card kpi-blue"><span>Toplam Eşleşme</span><strong>{adminRevenue.total_matches}</strong></div>
                <div className="kpi-card kpi-orange"><span>Ödenen</span><strong>{adminRevenue.paid_matches}</strong></div>
                <div className="kpi-card"><span>Ödenmemiş</span><strong style={{ color: "#ef4444" }}>{adminRevenue.unpaid_matches}</strong></div>
              </div>
              <div className="reports-grid">
                <div className="report-card">
                  <h3>📅 Aylık Gelir</h3>
                  <div className="stats-list">
                    {Object.entries(adminRevenue.monthly || {}).sort().map(([month, data]) => (
                      <div key={month} className="stats-row"><span className="stats-row-label">{month}</span><span className="stats-row-value">₺{data.revenue?.toLocaleString("tr-TR")} ({data.matches} eşleşme, {data.payments} ödeme)</span></div>
                    ))}
                  </div>
                </div>
                <div className="report-card">
                  <h3>🌍 Bölge Bazlı Gelir</h3>
                  <div className="stats-list">
                    {Object.entries(adminRevenue.region_breakdown || {}).map(([region, data]) => (
                      <div key={region} className="stats-row"><span className="stats-row-label">{region}</span><span className="stats-row-value">₺{data.revenue?.toLocaleString("tr-TR")} ({data.matches} eşleşme)</span></div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          ) : <div className="text-muted">Gelir verisi yok</div>}
        </div>
      )}

      {/* Regions Tab */}
      {tab === "regions" && !loading && (
        <div>
          <h2 style={{ marginBottom: "1rem" }}>🌍 Bölge Yönetimi</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
            {regionPricing.map((rp) => {
              const stats = regionStats?.[rp.region] || {};
              return (
                <div key={rp.region} className="card">
                  <h3>{rp.label}</h3>
                  <div className="stats-list" style={{ margin: "1rem 0" }}>
                    <div className="stats-row"><span className="stats-row-label">Otel Sayısı</span><span className="stats-row-value">{stats.hotels || 0}</span></div>
                    <div className="stats-row"><span className="stats-row-label">Aktif İlan</span><span className="stats-row-value">{stats.active_listings || 0}</span></div>
                    <div className="stats-row"><span className="stats-row-label">Toplam İlan</span><span className="stats-row-value">{stats.total_listings || 0}</span></div>
                    <div className="stats-row"><span className="stats-row-label">Varsayılan Ücret</span><span className="stats-row-value">₺{rp.default_fee}</span></div>
                    <div className="stats-row"><span className="stats-row-label">Aktif Ücret</span><span className="stats-row-value" style={{ fontWeight: 700, color: "#1a3a2a" }}>₺{rp.active_fee}</span></div>
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <input type="number" defaultValue={rp.active_fee} id={`fee-${rp.region}`} style={{ width: "100px", padding: "0.4rem" }} />
                    <button className="btn-primary btn-sm" onClick={() => updateRegionFee(rp.region, document.getElementById(`fee-${rp.region}`).value)}>Güncelle</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === "logs" && (
        <div>
          <h2 style={{ marginBottom: "1rem" }}>📜 Aktivite Logları</h2>
          {logLoading ? (
            <div className="page-center" style={{ height: 200 }}><span className="loading-spin" /></div>
          ) : activityLogs.length === 0 ? (
            <div className="empty-state"><div className="empty-state-icon">📜</div><div className="empty-state-title">Henüz aktivite yok</div></div>
          ) : (
            <div className="card">
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Tarih</th><th>Kullanıcı</th><th>İşlem</th><th>Nesne</th><th>Detay</th></tr></thead>
                  <tbody>
                    {activityLogs.map((log) => (
                      <tr key={log.id}>
                        <td style={{ whiteSpace: "nowrap" }}>{new Date(log.created_at).toLocaleString("tr-TR")}</td>
                        <td>{log.actor_name}</td>
                        <td><span className="chip">{log.action}</span></td>
                        <td>{log.entity}</td>
                        <td style={{ fontSize: "0.8rem", color: "#6b7c93", maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {JSON.stringify(log.metadata || {}).slice(0, 80)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ textAlign: "center", marginTop: "1rem" }}>
                <button className="btn-ghost btn-sm" onClick={() => {
                  setLogLoading(true);
                  axios.get(`/admin/activity-logs?limit=50&skip=${activityLogs.length}`).then(r => setActivityLogs(prev => [...prev, ...r.data])).catch(() => {}).finally(() => setLogLoading(false));
                }}>Daha Fazla Yükle</button>
              </div>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
};

export default AdminPage;
