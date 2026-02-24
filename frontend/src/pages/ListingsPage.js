import React from "react";
import { Link } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import { FEATURES_LIST, ROOM_TYPES, statusLabel, roomTypeLabel } from "@/utils/constants";

const ListingsPage = () => {
  const [listings, setListings] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [showFilters, setShowFilters] = React.useState(true);
  const [filters, setFilters] = React.useState({
    region: "",
    concept: "",
    pax_min: "",
    pax_max: "",
    price_min: "",
    price_max: "",
    avail_status: "",
    hide_expired: true,
    date_from: "",
    date_to: "",
    room_type: "",
    features: "",
    include_cross_region: false,
  });
  const navigate = useNavigate();

  const load = async (f) => {
    setLoading(true);
    try {
      const params = {};
      if (f.region) params.region = f.region;
      if (f.concept) params.concept = f.concept;
      if (f.pax_min) params.pax_min = parseInt(f.pax_min);
      if (f.pax_max) params.pax_max = parseInt(f.pax_max);
      if (f.price_min) params.price_min = parseFloat(f.price_min);
      if (f.price_max) params.price_max = parseFloat(f.price_max);
      if (f.avail_status) params.avail_status = f.avail_status;
      if (f.date_from) params.date_from = f.date_from;
      if (f.date_to) params.date_to = f.date_to;
      if (f.room_type) params.room_type = f.room_type;
      if (f.features) params.features = f.features;
      params.hide_expired = f.hide_expired;
      if (f.include_cross_region) params.include_cross_region = true;
      const res = await axios.get("/listings", { params });
      setListings(res.data);
    } catch {
      setListings([]);
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  React.useEffect(() => { load(filters); }, []);

  const handleFilter = (e) => {
    e.preventDefault();
    load(filters);
  };

  const resetFilters = () => {
    const fresh = { region: "", concept: "", pax_min: "", pax_max: "", price_min: "", price_max: "", avail_status: "", hide_expired: true, date_from: "", date_to: "", room_type: "", features: "", include_cross_region: false };
    setFilters(fresh);
    load(fresh);
  };

  return (
    <Layout>
      <div className="page-header">
        <h1 className="page-title" style={{ margin: 0 }}>Anonim Kapasite Listesi</h1>
        <span style={{ fontSize: "0.85rem", color: "#6b7c93" }}>{listings.length} ilan</span>
      </div>

      <div className="filter-panel">
        <div className="filter-panel-header" onClick={() => setShowFilters(!showFilters)}>
          <h3>🔍 Filtrele &amp; Ara</h3>
          <span style={{ fontSize: "0.8rem", color: "#6b7c93" }}>{showFilters ? "▲ Gizle" : "▼ Göster"}</span>
        </div>
        {showFilters && (
          <form onSubmit={handleFilter}>
            <div className="filter-row">
              <label className="field">
                <span>Bölge</span>
                <select value={filters.region} onChange={(e) => setFilters({ ...filters, region: e.target.value })}>
                  <option value="">Tümü</option>
                  <option value="Sapanca">Sapanca</option>
                  <option value="Kartepe">Kartepe</option>
                  <option value="Abant">Abant</option>
                  <option value="Ayder">Ayder</option>
                  <option value="Kas">Kaş</option>
                  <option value="Alacati">Alaçatı</option>
                </select>
              </label>
              <label className="field">
                <span>Oda Tipi</span>
                <select value={filters.room_type} onChange={(e) => setFilters({ ...filters, room_type: e.target.value })}>
                  <option value="">Tümü</option>
                  {ROOM_TYPES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Konsept / Ara</span>
                <input
                  value={filters.concept}
                  onChange={(e) => setFilters({ ...filters, concept: e.target.value })}
                  placeholder="Bungalov, Butik..."
                />
              </label>
              <label className="field">
                <span>Durum</span>
                <select value={filters.avail_status} onChange={(e) => setFilters({ ...filters, avail_status: e.target.value })}>
                  <option value="">Tümü</option>
                  <option value="available">Müsait</option>
                  <option value="limited">Sınırlı</option>
                  <option value="alternative">Alternatif</option>
                </select>
              </label>
            </div>
            <div className="filter-row">
              <label className="field">
                <span>Min. Kişi</span>
                <input type="number" min="1" value={filters.pax_min} onChange={(e) => setFilters({ ...filters, pax_min: e.target.value })} placeholder="Min" />
              </label>
              <label className="field">
                <span>Maks. Kişi</span>
                <input type="number" min="1" value={filters.pax_max} onChange={(e) => setFilters({ ...filters, pax_max: e.target.value })} placeholder="Maks" />
              </label>
              <label className="field">
                <span>Min. Fiyat (₺)</span>
                <input type="number" value={filters.price_min} onChange={(e) => setFilters({ ...filters, price_min: e.target.value })} placeholder="Min" />
              </label>
              <label className="field">
                <span>Maks. Fiyat (₺)</span>
                <input type="number" value={filters.price_max} onChange={(e) => setFilters({ ...filters, price_max: e.target.value })} placeholder="Maks" />
              </label>
            </div>
            <div className="filter-row">
              <label className="field">
                <span>Tarih Başlangıç</span>
                <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
              </label>
              <label className="field">
                <span>Tarih Bitiş</span>
                <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
              </label>
              <label className="field">
                <span>Özellikler</span>
                <input value={filters.features} onChange={(e) => setFilters({ ...filters, features: e.target.value })} placeholder="Jakuzi, Şömine..." />
              </label>
              <label className="field" style={{ justifyContent: "flex-end" }}>
                <span>&nbsp;</span>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem", cursor: "pointer", padding: "0.6rem 0" }}>
                  <input
                    type="checkbox"
                    checked={filters.hide_expired}
                    onChange={(e) => setFilters({ ...filters, hide_expired: e.target.checked })}
                  />
                  Geçmiş ilanları gizle
                </label>
              </label>
              <label className="field" style={{ justifyContent: "flex-end" }}>
                <span>&nbsp;</span>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem", cursor: "pointer", padding: "0.6rem 0" }}>
                  <input
                    type="checkbox"
                    checked={filters.include_cross_region}
                    onChange={(e) => setFilters({ ...filters, include_cross_region: e.target.checked })}
                  />
                  🌍 Bölgeler arası ilanları dahil et
                </label>
              </label>
            </div>
            <div className="filter-actions">
              <button type="button" className="btn-ghost btn-sm" onClick={resetFilters}>Sıfırla</button>
              <button type="submit" className="btn-primary btn-sm">Filtrele</button>
            </div>
          </form>
        )}
      </div>

      {loading ? (
        <div className="page-center" style={{ height: 200 }}>
          <span className="loading-spin" />
        </div>
      ) : listings.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <div className="empty-state-title">İlan bulunamadı</div>
          <div className="empty-state-sub">Filtreleri değiştirip tekrar deneyin.</div>
        </div>
      ) : (
        <div className="cards-grid">
          {listings.map((l) => (
            <div
              className="listing-card listing-card-clickable"
              key={l.id}
              data-testid="listing-card"
              onClick={() => navigate(`/listings/${l.id}`)}
            >
              {l.image_urls && l.image_urls.length > 0 ? (
                <div className="listing-image-wrapper">
                  <img src={l.image_urls[0]} alt="Kapasite görseli" className="listing-image" />
                </div>
              ) : (
                <div className="listing-image-wrapper" style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: "2rem" }}>
                  🏨
                </div>
              )}
              <div className="listing-card-inner">
                <div className="listing-header">
                  <span className="badge-region">{l.region} / {l.micro_location}</span>
                  <span className={`status-chip status-${l.availability_status}`}>
                    {statusLabel(l.availability_status)}
                  </span>
                </div>
                <div className="listing-body">
                  <div style={{ fontWeight: 600, color: "#1a3a2a", fontSize: "0.95rem" }}>{l.room_type ? roomTypeLabel(l.room_type) : l.concept}</div>
                  <div style={{ color: "#6b7c93", fontSize: "0.82rem" }}>{l.concept}</div>
                  <div>👥 {l.capacity_label} · {l.pax} kişi</div>
                  <div>📅 {new Date(l.date_start).toLocaleDateString("tr-TR")} – {new Date(l.date_end).toLocaleDateString("tr-TR")} ({l.nights} gece)</div>
                  {l.min_nights > 1 && <div style={{ fontSize: "0.8rem", color: "#6b7c93" }}>⏱ Min. {l.min_nights} gece</div>}
                  {l.breakfast_included && <div style={{ fontSize: "0.8rem", color: "#166534" }}>☕ Kahvaltı dahil</div>}
                  <div className="listing-price">{l.price_min.toLocaleString("tr-TR")} TL <span style={{ fontSize: "0.8rem", color: "#6b7c93", fontWeight: 400 }}>/gece</span></div>
                  {l.guest_restrictions && l.guest_restrictions.length > 0 && (
                    <div style={{ fontSize: "0.75rem", color: "#dc2626", marginTop: "0.2rem" }}>
                      🚫 {l.guest_restrictions.slice(0, 2).join(" · ")}{l.guest_restrictions.length > 2 && "..."}
                    </div>
                  )}
                  {l.features && l.features.length > 0 && (
                    <div className="listing-features">
                      {l.features.slice(0, 4).map((f) => (
                        <span key={f} className="feature-badge">{f}</span>
                      ))}
                      {l.features.length > 4 && (
                        <span className="feature-badge">+{l.features.length - 4}</span>
                      )}
                    </div>
                  )}
                </div>
                {l.is_locked && <div className="locked-badge">🔒 Şu an kilitli</div>}
                {l.allow_cross_region && <div style={{ position: "absolute", top: 8, right: 8, background: "#1d4ed8", color: "white", fontSize: "0.7rem", padding: "2px 8px", borderRadius: 20, fontWeight: 600 }}>🌍 Cross-Region</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
};

export default ListingsPage;
