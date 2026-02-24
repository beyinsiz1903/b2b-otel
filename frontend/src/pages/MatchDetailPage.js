import React from "react";
import { useParams, Link } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";

const MatchDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`/matches/${id}`);
        setData(res.data);
      } catch {
        setError("Bu eşleşme görüntülenemiyor veya yetkiniz yok.");
      }
    };
    load();
  }, [id]);

  const handleBack = () => location.key !== "default" ? navigate(-1) : navigate("/matches");

  if (error) {
    return (
      <Layout>
        <div className="error">{error}</div>
        <button className="btn-ghost mt-2" onClick={handleBack}>← Geri</button>
      </Layout>
    );
  }

  if (!data) {
    return (
      <Layout>
        <div className="page-center" style={{ height: 300 }}><span className="loading-spin" /></div>
      </Layout>
    );
  }

  const { reference_code, fee_amount, fee_status, accepted_at, counterparty, listing_snapshot } = data;
  const self = counterparty?.self || {};
  const other = counterparty?.other || {};

  const whatsappNum = other.whatsapp ? other.whatsapp.replace(/\D/g, "") : null;
  const whatsappUrl = whatsappNum ? `https://wa.me/${whatsappNum}` : null;

  return (
    <Layout>
      <div style={{ maxWidth: 900 }}>
        <button className="btn-ghost btn-sm" onClick={handleBack} style={{ marginBottom: "1rem" }}>
          ← Geri
        </button>

        <h1 className="page-title">Eşleşme Detayı</h1>

        <div className="cards-row" style={{ marginBottom: "1.5rem" }}>
          <div className="kpi-card kpi-green" data-testid="match-reference">
            <span>Referans Kodu</span>
            <strong style={{ fontSize: "1.2rem", fontFamily: "monospace" }}>{reference_code}</strong>
          </div>
          <div className="kpi-card">
            <span>Kabul Tarihi</span>
            <strong style={{ fontSize: "1rem" }}>{accepted_at ? new Date(accepted_at).toLocaleString("tr-TR") : "-"}</strong>
          </div>
          <div className="kpi-card kpi-orange" data-testid="match-fee">
            <span>Hizmet Bedeli</span>
            <strong>{fee_amount?.toLocaleString("tr-TR")} TL</strong>
            <div className="kpi-sub">
              {fee_status === "due" ? "⏳ Ödeme bekliyor" : fee_status === "paid" ? "✅ Ödendi" : "🎁 Silindi"}
            </div>
          </div>
        </div>

        {listing_snapshot && (
          <div style={{ marginBottom: "1.5rem" }}>
            <div className="section-title">📋 Eşleşen İlan Bilgisi</div>
            <div style={{ background: "#f0f9f5", borderRadius: "0.75rem", padding: "1rem", border: "1px solid #b2dfd0", display: "flex", gap: "1.5rem", flexWrap: "wrap", fontSize: "0.875rem" }}>
              <div><strong>Bölge:</strong> {listing_snapshot.region} / {listing_snapshot.micro_location}</div>
              <div><strong>Konsept:</strong> {listing_snapshot.concept}</div>
              <div><strong>Kapasite:</strong> {listing_snapshot.capacity_label} · {listing_snapshot.pax} kişi</div>
              {listing_snapshot.date_start && (
                <div><strong>Tarihler:</strong> {new Date(listing_snapshot.date_start).toLocaleDateString("tr-TR")} – {new Date(listing_snapshot.date_end).toLocaleDateString("tr-TR")} ({listing_snapshot.nights} gece)</div>
              )}
              <div><strong>Fiyat:</strong> {listing_snapshot.price_min?.toLocaleString("tr-TR")} TL/gece</div>
            </div>
          </div>
        )}

        <div className="section-title">🏨 Otel Bilgileri</div>
        <div className="match-detail-grid">
          <div className="match-hotel-card">
            <h3>Sizin Oteliniz</h3>
            <div className="match-hotel-name">{self.name}</div>
            <div className="match-hotel-info">
              <div className="match-hotel-info-row">
                <span className="match-hotel-info-label">Bölge</span>
                <span>{self.region} / {self.micro_location}</span>
              </div>
              <div className="match-hotel-info-row">
                <span className="match-hotel-info-label">Konsept</span>
                <span>{self.concept}</span>
              </div>
              <div className="match-hotel-info-row">
                <span className="match-hotel-info-label">Adres</span>
                <span>{self.address}</span>
              </div>
              <div className="match-hotel-info-row">
                <span className="match-hotel-info-label">Telefon</span>
                <span>{self.phone}</span>
              </div>
            </div>
          </div>

          <div className="match-hotel-card counterparty" data-testid="match-counterparty">
            <h3>Karşı Otel</h3>
            <div className="match-hotel-name">{other.name}</div>
            <div className="match-hotel-info">
              <div className="match-hotel-info-row">
                <span className="match-hotel-info-label">Bölge</span>
                <span>{other.region} / {other.micro_location}</span>
              </div>
              <div className="match-hotel-info-row">
                <span className="match-hotel-info-label">Konsept</span>
                <span>{other.concept}</span>
              </div>
              <div className="match-hotel-info-row">
                <span className="match-hotel-info-label">Adres</span>
                <span>{other.address}</span>
              </div>
              <div className="match-hotel-info-row">
                <span className="match-hotel-info-label">Telefon</span>
                <span>{other.phone}</span>
              </div>
              {other.whatsapp && (
                <div className="match-hotel-info-row">
                  <span className="match-hotel-info-label">WhatsApp</span>
                  <span>{other.whatsapp}</span>
                </div>
              )}
              {other.website && (
                <div className="match-hotel-info-row">
                  <span className="match-hotel-info-label">Web</span>
                  <span><a href={other.website} target="_blank" rel="noopener noreferrer" style={{ color: "#2e6b57" }}>{other.website}</a></span>
                </div>
              )}
              {other.contact_person && (
                <div className="match-hotel-info-row">
                  <span className="match-hotel-info-label">İrtibat</span>
                  <span>{other.contact_person}</span>
                </div>
              )}
            </div>
            {whatsappUrl && (
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="whatsapp-btn"
              >
                💬 WhatsApp'ta Mesaj Gönder
              </a>
            )}
            {other.phone && (
              <a
                href={`tel:${other.phone}`}
                style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", marginTop: "0.5rem", fontSize: "0.85rem", color: "#2e6b57", fontWeight: 600 }}
              >
                📞 {other.phone}
              </a>
            )}
          </div>
        </div>

        <div className="section-note" data-testid="match-note">
          Bu eşleşme, otel → otel kapasite paylaşımı için oluşturulmuştur. Son kullanıcıya satış yapılmaz;
          platform yalnızca B2B eşleşme ve talep yönetimi sağlar.
        </div>
      </div>
    </Layout>
  );
};

export default MatchDetailPage;
