import React from "react";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Modal from "@/components/Modal";
import { statusLabel, roomTypeLabel } from "@/utils/constants";

const RequestsPage = () => {
  const [incoming, setIncoming] = React.useState([]);
  const [outgoing, setOutgoing] = React.useState([]);
  const [tab, setTab] = React.useState("incoming");
  const [altModal, setAltModal] = React.useState(null); // for offer-alternative modal
  const [detailModal, setDetailModal] = React.useState(null); // for request detail
  const [loading, setLoading] = React.useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [inRes, outRes] = await Promise.all([
        axios.get("/requests/incoming"),
        axios.get("/requests/outgoing"),
      ]);
      setIncoming(inRes.data);
      setOutgoing(outRes.data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => { load(); }, []);

  const act = async (id, type) => {
    try {
      if (type === "accept") await axios.post(`/requests/${id}/accept`);
      if (type === "reject") await axios.post(`/requests/${id}/reject`);
      if (type === "cancel") await axios.post(`/requests/${id}/cancel`);
      if (type === "accept-alternative") await axios.post(`/requests/${id}/accept-alternative`);
      if (type === "reject-alternative") await axios.post(`/requests/${id}/reject-alternative`);
      await load();
    } catch (err) {
      alert(err.response?.data?.detail || "İşlem başarısız.");
    }
  };

  const pendingCount = incoming.filter((r) => r.status === "pending").length;

  return (
    <Layout>
      <div className="page-header">
        <h1 className="page-title" style={{ margin: 0 }}>B2B Talepler</h1>
      </div>

      <div className="tabs">
        <div className={`tab ${tab === "incoming" ? "active" : ""}`} onClick={() => setTab("incoming")}>
          📥 Gelen Talepler
          {pendingCount > 0 && <span className="notif-dot" />}
          {` (${incoming.length})`}
        </div>
        <div className={`tab ${tab === "outgoing" ? "active" : ""}`} onClick={() => setTab("outgoing")}>
          📤 Gönderilen Talepler ({outgoing.length})
        </div>
      </div>

      {loading ? (
        <div className="page-center" style={{ height: 200 }}><span className="loading-spin" /></div>
      ) : tab === "incoming" ? (
        <div className="requests-section-card">
          <div className="requests-section-header">
            <h2>Gelen Talepler</h2>
            <span className="text-sm text-muted">{incoming.length} talep</span>
          </div>
          {incoming.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📥</div>
              <div className="empty-state-title">Henüz gelen talep yok</div>
            </div>
          ) : (
            <table className="requests-table" data-testid="incoming-table">
              <thead>
                <tr>
                  <th>İlan</th>
                  <th>Misafir Tipi</th>
                  <th>Tarih</th>
                  <th>Durum</th>
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {incoming.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <button className="btn-ghost btn-sm" onClick={() => setDetailModal(r)} title="Detay gör">
                        {r.listing_id.slice(0, 8)}...
                      </button>
                    </td>
                    <td>{r.guest_type === "family" ? "👨‍👩‍👧 Aile" : r.guest_type === "couple" ? "💑 Çift" : "👥 Grup"}</td>
                    <td style={{ fontSize: "0.8rem", color: "#6b7c93" }}>
                      {new Date(r.created_at).toLocaleDateString("tr-TR")}
                    </td>
                    <td>
                      <span className={`status-chip status-${r.status}`} style={{ fontSize: "0.73rem" }}>
                        {statusLabel(r.status)}
                      </span>
                    </td>
                    <td>
                      <div className="request-actions">
                        {r.status === "pending" && (
                          <>
                            <button className="btn-primary btn-sm" onClick={() => act(r.id, "accept")} data-testid="incoming-accept">
                              ✅ Kabul
                            </button>
                            <button className="btn-warning btn-sm" onClick={() => setAltModal(r)}>
                              🔄 Alternatif
                            </button>
                            <button className="btn-danger btn-sm" onClick={() => act(r.id, "reject")} data-testid="incoming-reject">
                              ❌ Red
                            </button>
                          </>
                        )}
                        {r.status === "alternative_offered" && (
                          <span className="text-sm text-muted">Yanıt bekleniyor...</span>
                        )}
                        <button className="btn-ghost btn-sm" onClick={() => setDetailModal(r)} title="Detay">
                          👁️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <div className="requests-section-card">
          <div className="requests-section-header">
            <h2>Gönderilen Talepler</h2>
            <span className="text-sm text-muted">{outgoing.length} talep</span>
          </div>
          {outgoing.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📤</div>
              <div className="empty-state-title">Henüz gönderilmiş talebiniz yok</div>
              <div className="empty-state-sub">
                <Link to="/listings" className="btn-primary btn-sm mt-2" style={{ display: "inline-flex" }}>
                  İlanları Gözat
                </Link>
              </div>
            </div>
          ) : (
            <table className="requests-table" data-testid="outgoing-table">
              <thead>
                <tr>
                  <th>İlan</th>
                  <th>Misafir Tipi</th>
                  <th>Tarih</th>
                  <th>Durum</th>
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {outgoing.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <button className="btn-ghost btn-sm" onClick={() => setDetailModal(r)}>
                        {r.listing_id.slice(0, 8)}...
                      </button>
                    </td>
                    <td>{r.guest_type === "family" ? "👨‍👩‍👧 Aile" : r.guest_type === "couple" ? "💑 Çift" : "👥 Grup"}</td>
                    <td style={{ fontSize: "0.8rem", color: "#6b7c93" }}>
                      {new Date(r.created_at).toLocaleDateString("tr-TR")}
                    </td>
                    <td>
                      <span className={`status-chip status-${r.status}`} style={{ fontSize: "0.73rem" }}>
                        {statusLabel(r.status)}
                      </span>
                    </td>
                    <td>
                      <div className="request-actions">
                        {r.status === "alternative_offered" && (
                          <>
                            <button className="btn-primary btn-sm" onClick={() => act(r.id, "accept-alternative")}>
                              ✅ Alt. Kabul
                            </button>
                            <button className="btn-danger btn-sm" onClick={() => act(r.id, "reject-alternative")}>
                              ❌ Alt. Red
                            </button>
                            <button className="btn-ghost btn-sm" onClick={() => setDetailModal(r)}>👁️ Alt. Gör</button>
                          </>
                        )}
                        {(r.status === "pending" || r.status === "alternative_offered") && (
                          <button className="btn-ghost btn-sm" onClick={() => act(r.id, "cancel")}>
                            ↩️ İptal
                          </button>
                        )}
                        <button className="btn-ghost btn-sm" onClick={() => setDetailModal(r)}>👁️</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Alternative Offer Modal */}
      {altModal && (
        <AltOfferModal
          request={altModal}
          onClose={() => setAltModal(null)}
          onSent={async () => { setAltModal(null); await load(); }}
        />
      )}

      {/* Request Detail Modal */}
      {detailModal && (
        <RequestDetailModal
          request={detailModal}
          onClose={() => setDetailModal(null)}
        />
      )}
    </Layout>
  );
};

// ── Alternative Offer Modal ───────────────────────────────────────────────────
const AltOfferModal = ({ request, onClose, onSent }) => {
  const [form, setForm] = React.useState({
    notes: "", proposed_price_min: "", proposed_price_max: "",
    proposed_date_start: "", proposed_date_end: "",
  });
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const payload = {};
    if (form.notes) payload.notes = form.notes;
    if (form.proposed_price_min) payload.proposed_price_min = parseFloat(form.proposed_price_min);
    if (form.proposed_price_max) payload.proposed_price_max = parseFloat(form.proposed_price_max);
    if (form.proposed_date_start) payload.proposed_date_start = new Date(form.proposed_date_start).toISOString();
    if (form.proposed_date_end) payload.proposed_date_end = new Date(form.proposed_date_end).toISOString();
    try {
      await axios.post(`/requests/${request.id}/offer-alternative`, payload);
      onSent();
    } catch (err) {
      setError(err.response?.data?.detail || "İşlem başarısız.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="🔄 Alternatif Teklif Gönder"
      footer={
        <>
          <button className="btn-ghost" onClick={onClose}>İptal</button>
          <button className="btn-warning" onClick={handleSubmit} disabled={loading}>
            {loading ? <><span className="loading-spin" /> Gönderiliyor...</> : "Alternatif Teklif Gönder"}
          </button>
        </>
      }
    >
      <p className="text-sm text-muted" style={{ marginBottom: "0.5rem" }}>
        Bu isteğe tam olarak müsait değilseniz alternatif tarih veya fiyat teklifleyebilirsiniz.
        Karşı taraf teklifi kabul veya reddedebilir.
      </p>
      <div className="grid-2">
        <label className="field">
          <span>Önerilen Başlangıç Tarihi</span>
          <input name="proposed_date_start" type="date" value={form.proposed_date_start} onChange={onChange} />
        </label>
        <label className="field">
          <span>Önerilen Bitiş Tarihi</span>
          <input name="proposed_date_end" type="date" value={form.proposed_date_end} onChange={onChange} />
        </label>
      </div>
      <div className="grid-2">
        <label className="field">
          <span>Önerilen Fiyat Min (TL)</span>
          <input name="proposed_price_min" type="number" value={form.proposed_price_min} onChange={onChange} placeholder="Örn: 7000" />
        </label>
        <label className="field">
          <span>Önerilen Fiyat Max (TL)</span>
          <input name="proposed_price_max" type="number" value={form.proposed_price_max} onChange={onChange} placeholder="Örn: 9000" />
        </label>
      </div>
      <label className="field">
        <span>Not / Açıklama</span>
        <textarea name="notes" value={form.notes} onChange={onChange} rows={3} placeholder="Neden alternatif öneriyorsunuz?" />
      </label>
      {error && <div className="error">{error}</div>}
    </Modal>
  );
};

// ── Request Detail Modal ──────────────────────────────────────────────────────
const RequestDetailModal = ({ request, onClose }) => {
  const [listing, setListing] = React.useState(null);

  React.useEffect(() => {
    if (request.listing_id) {
      axios.get(`/listings/${request.listing_id}`).then((r) => setListing(r.data)).catch(() => {});
    }
  }, [request.listing_id]);

  const alt = request.alternative_payload;

  return (
    <Modal open={true} onClose={onClose} title="📋 Talep Detayı">
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <div>
          <div className="text-sm text-muted" style={{ marginBottom: "0.4rem" }}>DURUM</div>
          <span className={`status-chip status-${request.status}`}>{statusLabel(request.status)}</span>
        </div>

        <div className="grid-2">
          <div>
            <div className="text-sm text-muted">Misafir Tipi</div>
            <div style={{ fontWeight: 600 }}>
              {request.guest_type === "family" ? "👨‍👩‍👧 Aile" : request.guest_type === "couple" ? "💑 Çift" : "👥 Grup"}
            </div>
          </div>
          <div>
            <div className="text-sm text-muted">Onay Süresi</div>
            <div style={{ fontWeight: 600 }}>{request.confirm_window_minutes} dakika</div>
          </div>
        </div>

        {request.notes && (
          <div>
            <div className="text-sm text-muted">Not</div>
            <div style={{ padding: "0.5rem 0.75rem", background: "#f8fafc", borderRadius: "0.5rem", fontSize: "0.875rem" }}>
              {request.notes}
            </div>
          </div>
        )}

        {listing && (
          <div>
            <div className="text-sm text-muted" style={{ marginBottom: "0.5rem" }}>İLAN BİLGİSİ</div>
            <div style={{ background: "#f0f9f5", borderRadius: "0.75rem", padding: "0.85rem", border: "1px solid #b2dfd0" }}>
              <div style={{ fontWeight: 700, color: "#1a3a2a", marginBottom: "0.5rem" }}>{listing.concept}</div>
              <div className="text-sm" style={{ color: "#4a5568", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                <div>📍 {listing.region} / {listing.micro_location}</div>
                <div>📅 {new Date(listing.date_start).toLocaleDateString("tr-TR")} – {new Date(listing.date_end).toLocaleDateString("tr-TR")} ({listing.nights} gece)</div>
                <div>👥 {listing.capacity_label} · {listing.pax} kişi</div>
                <div>💰 {listing.price_min?.toLocaleString("tr-TR")} TL/gece</div>
                {listing.features && listing.features.length > 0 && (
                  <div className="listing-features" style={{ marginTop: "0.4rem" }}>
                    {listing.features.slice(0, 5).map((f) => <span key={f} className="feature-badge">{f}</span>)}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {alt && Object.keys(alt).length > 0 && (
          <div>
            <div className="text-sm text-muted" style={{ marginBottom: "0.5rem" }}>ALTERNATİF TEKLİF</div>
            <div className="alt-offer-panel">
              <h4>🔄 Karşı Otel Alternatif Önerdi</h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.875rem" }}>
                {alt.proposed_date_start && (
                  <div className="alt-offer-row">
                    <span className="alt-offer-label">Önerilen Tarihler:</span>
                    <span>
                      {new Date(alt.proposed_date_start).toLocaleDateString("tr-TR")} –{" "}
                      {alt.proposed_date_end ? new Date(alt.proposed_date_end).toLocaleDateString("tr-TR") : "?"}
                    </span>
                  </div>
                )}
                {(alt.proposed_price_min || alt.proposed_price_max) && (
                  <div className="alt-offer-row">
                    <span className="alt-offer-label">Önerilen Fiyat:</span>
                    <span>
                      {alt.proposed_price_min?.toLocaleString("tr-TR")} – {alt.proposed_price_max?.toLocaleString("tr-TR")} TL
                    </span>
                  </div>
                )}
                {alt.notes && (
                  <div className="alt-offer-row">
                    <span className="alt-offer-label">Not:</span>
                    <span>{alt.notes}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="text-sm text-muted">
          Oluşturulma: {new Date(request.created_at).toLocaleString("tr-TR")}
          {" "} · Son güncelleme: {new Date(request.updated_at).toLocaleString("tr-TR")}
        </div>
      </div>
    </Modal>
  );
};

export default RequestsPage;
