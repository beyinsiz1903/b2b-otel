import React from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Modal from "@/components/Modal";
import { statusLabel, roomTypeLabel } from "@/utils/constants";

const ListingDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [listing, setListing] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [guestType, setGuestType] = React.useState("family");
  const [notes, setNotes] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [successMsg, setSuccessMsg] = React.useState("");
  const [mainImg, setMainImg] = React.useState(0);

  React.useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`/listings/${id}`);
        setListing(res.data);
      } catch (e) {
        setError(e.response?.status === 404 ? "Bu kapasite artık bulunmuyor." : "Detay yüklenemedi.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const handleBack = () => location.key !== "default" ? navigate(-1) : navigate("/listings");

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!listing || listing.is_locked) return;
    try {
      setSubmitting(true);
      setSuccessMsg("");
      await axios.post("/requests", {
        listing_id: listing.id,
        guest_type: guestType,
        notes,
        confirm_window_minutes: 120,
      });
      setSuccessMsg("✅ Talep gönderildi! 120 dk içinde yanıt bekleniyor.");
    } catch (err) {
      setError(err.response?.data?.detail || "Talep gönderilirken hata oluştu.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="page-center" style={{ height: 300 }}>
          <span className="loading-spin" />
        </div>
      </Layout>
    );
  }

  if (error && !listing) {
    return (
      <Layout>
        <div className="error">{error}</div>
        <button className="btn-secondary mt-2" onClick={handleBack}>← Listeye Dön</button>
      </Layout>
    );
  }

  if (!listing) return null;

  const start = new Date(listing.date_start);
  const end = new Date(listing.date_end);

  return (
    <Layout>
      <div style={{ maxWidth: 900 }}>
        <button className="btn-ghost btn-sm" onClick={handleBack} style={{ marginBottom: "1rem" }}>
          ← Geri
        </button>

        <div className="detail-header-main">
          <div>
            <div className="detail-title-main">{listing.room_type ? roomTypeLabel(listing.room_type) : listing.concept}</div>
            <div style={{ color: "#6b7c93", fontSize: "0.9rem" }}>{listing.concept}</div>
            <div className="detail-subtitle">{listing.region} / {listing.micro_location}</div>
            <div className="detail-meta-row">
              <span>📅 {start.toLocaleDateString("tr-TR")} – {end.toLocaleDateString("tr-TR")} ({listing.nights} gece)</span>
              <span>👥 {listing.capacity_label} / {listing.pax} pax</span>
            </div>
          </div>
          <span className={`status-chip status-${listing.availability_status}`} style={{ fontSize: "0.85rem", padding: "0.4rem 1rem" }}>
            {statusLabel(listing.availability_status)}
          </span>
        </div>

        <div className="detail-layout">
          <div className="detail-media">
            {listing.image_urls && listing.image_urls.length > 0 ? (
              <div className="detail-gallery">
                <div className="detail-gallery-main">
                  <img src={listing.image_urls[mainImg]} alt="Kapasite" />
                </div>
                {listing.image_urls.length > 1 && (
                  <div className="detail-gallery-thumbs">
                    {listing.image_urls.map((url, i) => (
                      <img
                        key={url}
                        src={url}
                        alt="Thumb"
                        onClick={() => setMainImg(i)}
                        style={{ opacity: i === mainImg ? 1 : 0.65 }}
                      />
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="detail-gallery placeholder">Görsel eklenmedi</div>
            )}
          </div>

          <aside className="detail-meta-card">
            <div className="detail-price">
              {listing.price_min.toLocaleString("tr-TR")} TL
              <span style={{ fontSize: "0.85rem", fontWeight: 400, color: "#6b7c93" }}> /gece</span>
            </div>
            {listing.breakfast_included && (
              <div style={{ fontSize: "0.85rem", color: "#166534", fontWeight: 600 }}>☕ Kahvaltı dahil</div>
            )}
            {listing.min_nights > 1 && (
              <div style={{ fontSize: "0.85rem", color: "#6b7c93" }}>⏱ Minimum {listing.min_nights} gece konaklama</div>
            )}
            {listing.guest_restrictions && listing.guest_restrictions.length > 0 && (
              <div style={{ background: "#fff5f5", borderRadius: "0.5rem", padding: "0.6rem 0.75rem", border: "1px solid #fecaca" }}>
                <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#dc2626", marginBottom: "0.3rem" }}>🚫 Kısıtlamalar</div>
                {listing.guest_restrictions.map((r) => (
                  <div key={r} style={{ fontSize: "0.8rem", color: "#7f1d1d" }}>• {r}</div>
                ))}
              </div>
            )}
            {listing.notes && (
              <div style={{ fontSize: "0.85rem", color: "#4a5568", borderTop: "1px solid #e2e8f0", paddingTop: "0.75rem" }}>
                <strong>Not:</strong> {listing.notes}
              </div>
            )}
            {listing.is_locked && (
              <div className="detail-locked">🔒 Bu kapasite şu an kilitli.</div>
            )}
          </aside>
        </div>

        {listing.features && listing.features.length > 0 && (
          <div className="detail-section">
            <h2>✨ Özellikler &amp; İmkanlar</h2>
            <div className="listing-features">
              {listing.features.map((f) => (
                <span key={f} className="feature-badge">{f}</span>
              ))}
            </div>
          </div>
        )}

        <div className="detail-section">
          <h2>📋 Talep Oluştur</h2>
          {successMsg && <div className="success mb-2">{successMsg}</div>}
          {error && <div className="error mb-2">{error}</div>}
          <form onSubmit={handleSubmit} className="detail-request-form">
            <label className="field">
              <span>Misafir Tipi</span>
              <select value={guestType} onChange={(e) => setGuestType(e.target.value)}>
                <option value="family">👨‍👩‍👧 Aile</option>
                <option value="couple">💑 Çift</option>
                <option value="group">👥 Grup</option>
              </select>
            </label>
            <label className="field">
              <span>Not (opsiyonel)</span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Misafirle ilgili özel not..."
                rows={3}
              />
            </label>
            <div className="field-help">⏱ Onay süresi: 120 dakika</div>
            <button
              className="btn-primary"
              type="submit"
              disabled={listing.is_locked || submitting || !!successMsg}
              data-testid="request-submit"
            >
              {listing.is_locked ? "🔒 Şu an kilitli" : submitting ? <><span className="loading-spin" /> Gönderiliyor...</> : "Talep Gönder"}
            </button>
          </form>
        </div>

        <div className="section-note" data-testid="anon-note">
          🔒 Bu ilan anonimdir. Otel adı ve iletişim bilgileri yalnızca eşleşme onaylandıktan sonra açılır.
        </div>
      </div>
    </Layout>
  );
};

export default ListingDetailPage;
