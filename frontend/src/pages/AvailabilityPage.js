import React from "react";
import { useNavigate } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Modal from "@/components/Modal";
import ConfirmDialog from "@/components/ConfirmDialog";
import ImageUploader from "@/components/ImageUploader";
import {
  FEATURES_LIST, ROOM_TYPES, GUEST_RESTRICTIONS_LIST,
  statusLabel, roomTypeLabel,
} from "@/utils/constants";

const AvailabilityPage = () => {
  const emptyForm = {
    region: "Sapanca", micro_location: "", concept: "",
    room_type: "bungalov", capacity_label: "2+1", pax: 2,
    date_start: "", date_end: "", nights: 1,
    price_min: 0, availability_status: "available",
    breakfast_included: false, min_nights: 1,
    image_urls_raw: "", features_raw: "", restrictions_raw: "", notes: "",
    template_id: "", allow_cross_region: false,
  };
  const [form, setForm] = React.useState(emptyForm);
  const [mine, setMine] = React.useState([]);
  const [templates, setTemplates] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [success, setSuccess] = React.useState("");
  const [editModal, setEditModal] = React.useState(null);
  const [deleteConfirm, setDeleteConfirm] = React.useState(null);
  const [tplDeleteConfirm, setTplDeleteConfirm] = React.useState(null);
  const [tplEditModal, setTplEditModal] = React.useState(null);
  const [tplCreateModal, setTplCreateModal] = React.useState(false);
  const [tab, setTab] = React.useState("create");

  const onChange = (e) => {
    const val = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm({ ...form, [e.target.name]: val });
  };

  const loadMine = async () => {
    try { const res = await axios.get("/listings/mine"); setMine(res.data); } catch { setMine([]); }
  };
  const loadTemplates = async () => {
    try { const res = await axios.get("/room-templates"); setTemplates(res.data); } catch { setTemplates([]); }
  };

  React.useEffect(() => { loadMine(); loadTemplates(); }, []);

  // Şablondan form doldur
  const applyTemplate = (tpl) => {
    setForm({
      ...form,
      region: tpl.region,
      micro_location: tpl.micro_location,
      concept: tpl.concept,
      room_type: tpl.room_type,
      capacity_label: tpl.capacity_label,
      pax: tpl.pax,
      breakfast_included: tpl.breakfast_included,
      min_nights: tpl.min_nights,
      features_raw: (tpl.features || []).join(", "),
      restrictions_raw: (tpl.guest_restrictions || []).join(", "),
      image_urls_raw: (tpl.image_urls || []).join(", "),
      notes: tpl.notes || "",
      price_min: tpl.price_suggestion || 0,
      template_id: tpl.id,
    });
    setSuccess(`✅ "${tpl.name}" şablonu yüklendi. Tarih ve fiyatı girin.`);
  };

  const addFeature = (chip) => {
    const current = form.features_raw ? form.features_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
    if (!current.includes(chip)) setForm({ ...form, features_raw: [...current, chip].join(", ") });
  };
  const addRestriction = (chip) => {
    const current = form.restrictions_raw ? form.restrictions_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
    if (!current.includes(chip)) setForm({ ...form, restrictions_raw: [...current, chip].join(", ") });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setSuccess(""); setLoading(true);
    try {
      const image_urls = form.image_urls_raw ? form.image_urls_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
      const features = form.features_raw ? form.features_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
      const guest_restrictions = form.restrictions_raw ? form.restrictions_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
      await axios.post("/listings", {
        region: form.region, micro_location: form.micro_location, concept: form.concept,
        capacity_label: form.capacity_label, pax: Number(form.pax),
        date_start: new Date(form.date_start).toISOString(),
        date_end: new Date(form.date_end).toISOString(),
        nights: Number(form.nights), price_min: Number(form.price_min), price_max: Number(form.price_min),
        availability_status: form.availability_status,
        room_type: form.room_type,
        breakfast_included: form.breakfast_included,
        min_nights: Number(form.min_nights),
        image_urls, features, guest_restrictions, notes: form.notes,
        template_id: form.template_id || null,
        allow_cross_region: form.allow_cross_region,
      });
      setSuccess("✅ Kapasite ilanı yayınlandı!");
      setForm({ ...emptyForm });
      await loadMine();
      setTab("mine");
    } catch (err) {
      setError(err.response?.data?.detail || "İlan oluşturulamadı.");
    } finally { setLoading(false); }
  };

  const handleDelete = async (id) => {
    try { await axios.delete(`/listings/${id}`); await loadMine(); setDeleteConfirm(null); }
    catch (err) { alert(err.response?.data?.detail || "Silinemedi."); }
  };
  const handleTplDelete = async (id) => {
    try { await axios.delete(`/room-templates/${id}`); await loadTemplates(); setTplDeleteConfirm(null); }
    catch (err) { alert(err.response?.data?.detail || "Silinemedi."); }
  };

  return (
    <Layout>
      <h1 className="page-title">Kendi Kapasitelerim</h1>

      <div className="tabs">
        <div className={`tab ${tab === "create" ? "active" : ""}`} onClick={() => setTab("create")}>
          + Yeni İlan Oluştur
        </div>
        <div className={`tab ${tab === "mine" ? "active" : ""}`} onClick={() => setTab("mine")}>
          📋 İlanlarım ({mine.length})
        </div>
        <div className={`tab ${tab === "templates" ? "active" : ""}`} onClick={() => setTab("templates")}>
          🗂 Oda Şablonlarım ({templates.length})
        </div>
      </div>

      {/* ── YENİ İLAN OLUŞTUR ── */}
      {tab === "create" && (
        <>
          <div className="info-banner">
            <strong>🔒 Anonim ilan</strong>
            Otel adı ve iletişim bilgisi eşleşme olmadan açılmaz. Görsellerde isim/logo kullanmayın.
          </div>

          {/* Şablon seçici */}
          {templates.length > 0 && (
            <div style={{ background: "#f0f9f5", border: "1px solid #b2dfd0", borderRadius: "0.75rem", padding: "1rem", marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#1a3a2a", marginBottom: "0.6rem" }}>
                🗂 Kayıtlı Şablondan Oluştur
              </div>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {templates.map((tpl) => (
                  <button
                    key={tpl.id}
                    type="button"
                    className="btn-secondary btn-sm"
                    onClick={() => applyTemplate(tpl)}
                    title={`${roomTypeLabel(tpl.room_type)} · ${tpl.capacity_label} · ${tpl.pax} kişi`}
                  >
                    {roomTypeLabel(tpl.room_type)} — {tpl.name}
                  </button>
                ))}
              </div>
              <div className="field-help" style={{ marginTop: "0.4rem" }}>Butona tıklayınca form otomatik dolar, sadece tarih ve fiyat girmeniz yeter.</div>
            </div>
          )}

          <form className="availability-form" onSubmit={handleSubmit} data-testid="availability-form">
            {/* Bölge / Lokasyon / Konsept */}
            <div className="grid-3">
              <label className="field">
                <span>Bölge</span>
                <select name="region" value={form.region} onChange={onChange}>
                  <option value="Sapanca">Sapanca</option>
                  <option value="Kartepe">Kartepe</option>
                  <option value="Abant">Abant</option>
                  <option value="Ayder">Ayder</option>
                  <option value="Kas">Kaş</option>
                  <option value="Alacati">Alaçatı</option>
                </select>
              </label>
              <label className="field">
                <span>Mikro Lokasyon</span>
                <input name="micro_location" value={form.micro_location} onChange={onChange} required placeholder="Örn: Sapanca Gölü kıyısı" />
              </label>
              <label className="field">
                <span>Konsept</span>
                <input name="concept" value={form.concept} onChange={onChange} required placeholder="Bungalov, Butik, Resort..." />
              </label>
            </div>

            {/* Oda Tipi / Kapasite / Kişi / Durum */}
            <div className="grid-4">
              <label className="field">
                <span>Oda Tipi</span>
                <select name="room_type" value={form.room_type} onChange={onChange}>
                  {ROOM_TYPES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Kapasite Etiketi</span>
                <input name="capacity_label" value={form.capacity_label} onChange={onChange} placeholder="2+1, 4+2..." />
              </label>
              <label className="field">
                <span>Kişi Sayısı</span>
                <input name="pax" type="number" min="1" value={form.pax} onChange={onChange} />
              </label>
              <label className="field">
                <span>Durum</span>
                <select name="availability_status" value={form.availability_status} onChange={onChange}>
                  <option value="available">Müsait</option>
                  <option value="limited">Sınırlı</option>
                  <option value="alternative">Alternatif</option>
                </select>
              </label>
            </div>

            {/* Tarihler / Gece / Min Konaklama / Fiyat */}
            <div className="grid-4">
              <label className="field">
                <span>Başlangıç Tarihi</span>
                <input name="date_start" type="date" value={form.date_start} onChange={onChange} required />
              </label>
              <label className="field">
                <span>Bitiş Tarihi</span>
                <input name="date_end" type="date" value={form.date_end} onChange={onChange} required />
              </label>
              <label className="field">
                <span>Gece Sayısı</span>
                <input name="nights" type="number" min="1" value={form.nights} onChange={onChange} />
              </label>
              <label className="field">
                <span>Min. Konaklama (gece)</span>
                <input name="min_nights" type="number" min="1" value={form.min_nights} onChange={onChange} />
                <span className="field-help">En az kaç gece kalınmalı?</span>
              </label>
            </div>

            {/* Fiyat + Kahvaltı */}
            <div className="grid-2">
              <label className="field">
                <span>Fiyat (TL/gece)</span>
                <input name="price_min" type="number" min="0" value={form.price_min} onChange={onChange} />
              </label>
              <label className="field">
                <span>Kahvaltı</span>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.6rem 0", cursor: "pointer" }}>
                  <input type="checkbox" name="breakfast_included" checked={form.breakfast_included} onChange={onChange} />
                  <span style={{ fontWeight: 600 }}>Kahvaltı dahil</span>
                </label>
              </label>
            </div>

            {/* Misafir Kısıtlamaları */}
            <label className="field">
              <span>Misafir Kısıtlamaları</span>
              <textarea
                name="restrictions_raw"
                value={form.restrictions_raw}
                onChange={onChange}
                placeholder="Örn: Evcil hayvan kabul edilmez, 18 yaş üstü..."
                rows={2}
              />
              <div style={{ marginTop: "0.4rem" }}>
                {GUEST_RESTRICTIONS_LIST.map((r) => {
                  const sel = form.restrictions_raw.split(",").map((s) => s.trim()).includes(r);
                  return (
                    <button key={r} type="button" className={`feature-chip ${sel ? "selected" : ""}`} onClick={() => addRestriction(r)}>
                      {sel ? "✓ " : ""}{r}
                    </button>
                  );
                })}
              </div>
            </label>

            {/* Özellikler */}
            <label className="field">
              <span>Özellikler &amp; İmkânlar</span>
              <textarea name="features_raw" value={form.features_raw} onChange={onChange} placeholder="Şömine, Göl manzarası, Jakuzili..." rows={2} />
              <div style={{ marginTop: "0.4rem" }}>
                {FEATURES_LIST.map((chip) => {
                  const sel = form.features_raw.split(",").map((s) => s.trim()).includes(chip);
                  return (
                    <button key={chip} type="button" className={`feature-chip ${sel ? "selected" : ""}`} onClick={() => addFeature(chip)}>
                      {sel ? "✓ " : ""}{chip}
                    </button>
                  );
                })}
              </div>
            </label>

            {/* Resimler / Not */}
            <ImageUploader
              value={form.image_urls_raw}
              onChange={(val) => setForm({ ...form, image_urls_raw: val })}
              label="Resimler (dosyadan yükle veya URL ekle)"
            />

            {/* Bölgeler Arası Paylaşım */}
            <label className="field" style={{ display: "flex", alignItems: "center", gap: "0.75rem", cursor: "pointer" }}>
              <input type="checkbox" checked={form.allow_cross_region} onChange={(e) => setForm({ ...form, allow_cross_region: e.target.checked })} style={{ width: 20, height: 20 }} />
              <span style={{ fontWeight: 600 }}>🌍 Bölgeler arası paylaşıma aç</span>
              <span style={{ fontSize: "0.8rem", color: "#6b7c93" }}>Diğer bölgelerdeki oteller de bu ilanı görebilir ve talep gönderebilir</span>
            </label>

            <label className="field">
              <span>Ek Not (opsiyonel)</span>
              <textarea name="notes" value={form.notes} onChange={onChange} placeholder="Misafire iletmek istediğiniz özel not..." rows={2} />
            </label>

            {error && <div className="error">{error}</div>}
            {success && <div className="success">{success}</div>}
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
              <button className="btn-primary" type="submit" disabled={loading} data-testid="availability-submit">
                {loading ? <><span className="loading-spin" /> Yayınlanıyor...</> : "📢 Kapasite Yayınla"}
              </button>
              <button type="button" className="btn-ghost btn-sm" onClick={() => setForm(emptyForm)}>Formu Temizle</button>
            </div>
          </form>
        </>
      )}

      {/* ── İLANLARIM ── */}
      {tab === "mine" && (
        mine.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-title">Henüz ilanınız yok</div>
            <button className="btn-primary mt-3" onClick={() => setTab("create")}>+ Yeni İlan Oluştur</button>
          </div>
        ) : (
          <div className="cards-grid">
            {mine.map((l) => {
              const expired = new Date(l.date_end) < new Date();
              return (
                <div key={l.id} className="own-listing-card" style={{ opacity: expired ? 0.7 : 1 }}>
                  {l.image_urls && l.image_urls.length > 0 ? (
                    <div className="listing-image-wrapper"><img src={l.image_urls[0]} alt="Kapasite" className="listing-image" /></div>
                  ) : (
                    <div className="listing-image-wrapper" style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: "2rem" }}>
                      {roomTypeLabel(l.room_type) || "🏨"}
                    </div>
                  )}
                  <div className="listing-card-inner">
                    <div className="listing-header">
                      <span className="badge-region">{l.region} / {l.micro_location}</span>
                      <div style={{ display: "flex", gap: "0.35rem", flexDirection: "column", alignItems: "flex-end" }}>
                        <span className={`status-chip status-${l.availability_status}`}>{statusLabel(l.availability_status)}</span>
                        {expired && <span style={{ fontSize: "0.7rem", color: "#dc2626", fontWeight: 600 }}>Süresi Geçti</span>}
                        {l.is_locked && <span style={{ fontSize: "0.7rem", color: "#d97706", fontWeight: 600 }}>🔒 Kilitli</span>}
                        {l.allow_cross_region && <span style={{ fontSize: "0.7rem", color: "#1d4ed8", fontWeight: 600 }}>🌍 Cross-Region</span>}
                      </div>
                    </div>
                    <div className="listing-body">
                      <div style={{ fontWeight: 600, color: "#1a3a2a" }}>{l.room_type ? roomTypeLabel(l.room_type) : l.concept}</div>
                      <div style={{ color: "#6b7c93", fontSize: "0.82rem" }}>{l.concept}</div>
                      <div>👥 {l.capacity_label} · {l.pax} kişi</div>
                      <div>📅 {new Date(l.date_start).toLocaleDateString("tr-TR")} – {new Date(l.date_end).toLocaleDateString("tr-TR")}</div>
                      {l.min_nights > 1 && <div style={{ fontSize: "0.8rem", color: "#6b7c93" }}>⏱ Min. {l.min_nights} gece</div>}
                      {l.breakfast_included && <div style={{ fontSize: "0.8rem", color: "#166534" }}>☕ Kahvaltı dahil</div>}
                      <div className="listing-price">{l.price_min.toLocaleString("tr-TR")} TL/gece</div>
                      {l.guest_restrictions && l.guest_restrictions.length > 0 && (
                        <div style={{ fontSize: "0.78rem", color: "#dc2626", marginTop: "0.25rem" }}>
                          🚫 {l.guest_restrictions.join(" · ")}
                        </div>
                      )}
                      {l.features && l.features.length > 0 && (
                        <div className="listing-features">
                          {l.features.slice(0, 3).map((f) => <span key={f} className="feature-badge">{f}</span>)}
                          {l.features.length > 3 && <span className="feature-badge">+{l.features.length - 3}</span>}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="own-listing-actions">
                    <button className="btn-secondary btn-sm" onClick={() => setEditModal(l)} disabled={l.is_locked}>✏️ Düzenle</button>
                    <button className="btn-danger btn-sm" onClick={() => setDeleteConfirm(l)} disabled={l.is_locked}>🗑️ Sil</button>
                  </div>
                </div>
              );
            })}
          </div>
        )
      )}

      {/* ── ODA ŞABLONLARIM ── */}
      {tab === "templates" && (
        <>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "1rem" }}>
            <button className="btn-primary" onClick={() => setTplCreateModal(true)}>
              + Yeni Şablon Oluştur
            </button>
          </div>
          <div className="info-banner">
            <strong>🗂 Oda Şablonları Nedir?</strong>
            Otelinizin odalarını bir kez kaydedin. İlan açarken "Şablondan Seç" ile tüm bilgiler otomatik dolar — sadece tarih ve fiyat girmeniz yeter.
          </div>
          {templates.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🗂</div>
              <div className="empty-state-title">Henüz şablon eklemediniz</div>
              <div className="empty-state-sub">Odalarınızı şablon olarak kaydedin, her seferinde doldurmayın.</div>
              <button className="btn-primary mt-3" onClick={() => setTplCreateModal(true)}>+ İlk Şablonu Oluştur</button>
            </div>
          ) : (
            <div className="cards-grid">
              {templates.map((tpl) => (
                <div key={tpl.id} className="own-listing-card">
                  {tpl.image_urls && tpl.image_urls.length > 0 ? (
                    <div className="listing-image-wrapper"><img src={tpl.image_urls[0]} alt={tpl.name} className="listing-image" /></div>
                  ) : (
                    <div className="listing-image-wrapper" style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: "2.5rem" }}>
                      {ROOM_TYPES.find((r) => r.value === tpl.room_type)?.label.split(" ")[0] || "🏨"}
                    </div>
                  )}
                  <div className="listing-card-inner">
                    <div className="listing-header">
                      <span className="badge-region">{tpl.region} / {tpl.micro_location}</span>
                      <span style={{ fontSize: "0.78rem", background: "#ede9fe", color: "#5b21b6", borderRadius: "999px", padding: "0.15rem 0.5rem", fontWeight: 600 }}>
                        {roomTypeLabel(tpl.room_type)}
                      </span>
                    </div>
                    <div className="listing-body">
                      <div style={{ fontWeight: 700, fontSize: "1rem", color: "#1a3a2a" }}>{tpl.name}</div>
                      <div style={{ color: "#6b7c93" }}>{tpl.concept}</div>
                      <div>👥 {tpl.capacity_label} · {tpl.pax} kişi</div>
                      {tpl.min_nights > 1 && <div style={{ fontSize: "0.8rem" }}>⏱ Min. {tpl.min_nights} gece</div>}
                      {tpl.breakfast_included && <div style={{ fontSize: "0.8rem", color: "#166534" }}>☕ Kahvaltı dahil</div>}
                      {tpl.price_suggestion > 0 && (
                        <div style={{ fontWeight: 600, color: "#2e6b57" }}>Öneri: {tpl.price_suggestion?.toLocaleString("tr-TR")} TL/gece</div>
                      )}
                      {tpl.guest_restrictions && tpl.guest_restrictions.length > 0 && (
                        <div style={{ fontSize: "0.78rem", color: "#dc2626" }}>🚫 {tpl.guest_restrictions.join(" · ")}</div>
                      )}
                      {tpl.features && tpl.features.length > 0 && (
                        <div className="listing-features">
                          {tpl.features.slice(0, 3).map((f) => <span key={f} className="feature-badge">{f}</span>)}
                          {tpl.features.length > 3 && <span className="feature-badge">+{tpl.features.length - 3}</span>}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="own-listing-actions">
                    <button
                      className="btn-primary btn-sm"
                      onClick={() => { applyTemplate(tpl); setTab("create"); }}
                    >
                      📢 İlan Oluştur
                    </button>
                    <button className="btn-secondary btn-sm" onClick={() => setTplEditModal(tpl)}>✏️</button>
                    <button className="btn-danger btn-sm" onClick={() => setTplDeleteConfirm(tpl)}>🗑️</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {editModal && (
        <EditListingModal listing={editModal} onClose={() => setEditModal(null)} onSaved={async () => { setEditModal(null); await loadMine(); }} />
      )}
      <ConfirmDialog open={!!deleteConfirm} title="İlanı Sil" message={`"${deleteConfirm?.concept}" ilanını silmek istediğinize emin misiniz?`} onConfirm={() => handleDelete(deleteConfirm.id)} onCancel={() => setDeleteConfirm(null)} confirmLabel="Sil" />

      {tplCreateModal && (
        <RoomTemplateModal onClose={() => setTplCreateModal(false)} onSaved={async () => { setTplCreateModal(false); await loadTemplates(); }} />
      )}
      {tplEditModal && (
        <RoomTemplateModal template={tplEditModal} onClose={() => setTplEditModal(null)} onSaved={async () => { setTplEditModal(null); await loadTemplates(); }} />
      )}
      <ConfirmDialog open={!!tplDeleteConfirm} title="Şablonu Sil" message={`"${tplDeleteConfirm?.name}" şablonunu silmek istediğinize emin misiniz?`} onConfirm={() => handleTplDelete(tplDeleteConfirm.id)} onCancel={() => setTplDeleteConfirm(null)} confirmLabel="Sil" />
    </Layout>
  );
};

// ── Room Template Modal ───────────────────────────────────────────────────────
const RoomTemplateModal = ({ template, onClose, onSaved }) => {
  const emptyTpl = {
    name: "", room_type: "bungalov", region: "Sapanca", micro_location: "",
    concept: "", capacity_label: "2+1", pax: 2,
    breakfast_included: false, min_nights: 1,
    features_raw: "", restrictions_raw: "", image_urls_raw: "",
    price_suggestion: "", notes: "",
  };
  const [form, setForm] = React.useState(
    template ? {
      name: template.name, room_type: template.room_type,
      region: template.region, micro_location: template.micro_location,
      concept: template.concept, capacity_label: template.capacity_label,
      pax: template.pax, breakfast_included: template.breakfast_included,
      min_nights: template.min_nights,
      features_raw: (template.features || []).join(", "),
      restrictions_raw: (template.guest_restrictions || []).join(", "),
      image_urls_raw: (template.image_urls || []).join(", "),
      price_suggestion: template.price_suggestion || "",
      notes: template.notes || "",
    } : emptyTpl
  );
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const onChange = (e) => {
    const val = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm({ ...form, [e.target.name]: val });
  };
  const addFeature = (chip) => {
    const cur = form.features_raw ? form.features_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
    if (!cur.includes(chip)) setForm({ ...form, features_raw: [...cur, chip].join(", ") });
  };
  const addRestriction = (chip) => {
    const cur = form.restrictions_raw ? form.restrictions_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
    if (!cur.includes(chip)) setForm({ ...form, restrictions_raw: [...cur, chip].join(", ") });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    const payload = {
      name: form.name, room_type: form.room_type, region: form.region,
      micro_location: form.micro_location, concept: form.concept,
      capacity_label: form.capacity_label, pax: Number(form.pax),
      breakfast_included: form.breakfast_included, min_nights: Number(form.min_nights),
      features: form.features_raw ? form.features_raw.split(",").map((s) => s.trim()).filter(Boolean) : [],
      guest_restrictions: form.restrictions_raw ? form.restrictions_raw.split(",").map((s) => s.trim()).filter(Boolean) : [],
      image_urls: form.image_urls_raw ? form.image_urls_raw.split(",").map((s) => s.trim()).filter(Boolean) : [],
      price_suggestion: form.price_suggestion ? Number(form.price_suggestion) : null,
      notes: form.notes || null,
    };
    try {
      if (template) { await axios.put(`/room-templates/${template.id}`, payload); }
      else { await axios.post("/room-templates", payload); }
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || "İşlem başarısız.");
    } finally { setLoading(false); }
  };

  return (
    <Modal
      open={true} onClose={onClose} size="lg"
      title={template ? "✏️ Şablonu Düzenle" : "🗂 Yeni Oda Şablonu"}
      footer={
        <>
          <button className="btn-ghost" onClick={onClose}>İptal</button>
          <button className="btn-primary" onClick={handleSave} disabled={loading}>
            {loading ? <><span className="loading-spin" /> Kaydediliyor...</> : "💾 Kaydet"}
          </button>
        </>
      }
    >
      <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
        <div className="info-banner" style={{ marginBottom: 0 }}>
          Şablonu bir kez kaydedin. İlan açarken seçip sadece tarih &amp; fiyat girin.
        </div>

        <label className="field">
          <span>Şablon Adı (sadece size görünür)</span>
          <input name="name" value={form.name} onChange={onChange} required placeholder="Örn: Göl Manzaralı Bungalov, Jakuzili Süit..." />
          <span className="field-help">Bu isim sadece sizin iç kullanımınız için, misafirlere gösterilmez.</span>
        </label>

        <div className="grid-3">
          <label className="field">
            <span>Oda Tipi</span>
            <select name="room_type" value={form.room_type} onChange={onChange}>
              {ROOM_TYPES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Bölge</span>
            <select name="region" value={form.region} onChange={onChange}>
              <option value="Sapanca">Sapanca</option>
              <option value="Kartepe">Kartepe</option>
              <option value="Abant">Abant</option>
              <option value="Ayder">Ayder</option>
              <option value="Kas">Kaş</option>
              <option value="Alacati">Alaçatı</option>
            </select>
          </label>
          <label className="field">
            <span>Mikro Lokasyon</span>
            <input name="micro_location" value={form.micro_location} onChange={onChange} required placeholder="Göl kıyısı..." />
          </label>
        </div>

        <div className="grid-3">
          <label className="field">
            <span>Konsept</span>
            <input name="concept" value={form.concept} onChange={onChange} required placeholder="Bungalov, Butik..." />
          </label>
          <label className="field">
            <span>Kapasite Etiketi</span>
            <input name="capacity_label" value={form.capacity_label} onChange={onChange} placeholder="2+1, 4+2..." />
          </label>
          <label className="field">
            <span>Kişi Sayısı</span>
            <input name="pax" type="number" min="1" value={form.pax} onChange={onChange} />
          </label>
        </div>

        <div className="grid-3">
          <label className="field">
            <span>Min. Konaklama (gece)</span>
            <input name="min_nights" type="number" min="1" value={form.min_nights} onChange={onChange} />
          </label>
          <label className="field">
            <span>Fiyat Önerisi (TL/gece)</span>
            <input name="price_suggestion" type="number" min="0" value={form.price_suggestion} onChange={onChange} placeholder="İlan açarken otomatik dolar" />
          </label>
          <label className="field">
            <span>Kahvaltı</span>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.6rem 0", cursor: "pointer" }}>
              <input type="checkbox" name="breakfast_included" checked={form.breakfast_included} onChange={onChange} />
              <span style={{ fontWeight: 600 }}>Kahvaltı dahil</span>
            </label>
          </label>
        </div>

        <label className="field">
          <span>Misafir Kısıtlamaları</span>
          <textarea name="restrictions_raw" value={form.restrictions_raw} onChange={onChange} rows={2} placeholder="Evcil hayvan kabul edilmez, 18 yaş üstü..." />
          <div style={{ marginTop: "0.4rem" }}>
            {GUEST_RESTRICTIONS_LIST.map((r) => {
              const sel = form.restrictions_raw.split(",").map((s) => s.trim()).includes(r);
              return <button key={r} type="button" className={`feature-chip ${sel ? "selected" : ""}`} onClick={() => addRestriction(r)}>{sel ? "✓ " : ""}{r}</button>;
            })}
          </div>
        </label>

        <label className="field">
          <span>Özellikler &amp; İmkânlar</span>
          <textarea name="features_raw" value={form.features_raw} onChange={onChange} rows={2} placeholder="Jakuzili, Şömine, Göl manzarası..." />
          <div style={{ marginTop: "0.4rem" }}>
            {FEATURES_LIST.map((chip) => {
              const sel = form.features_raw.split(",").map((s) => s.trim()).includes(chip);
              return <button key={chip} type="button" className={`feature-chip ${sel ? "selected" : ""}`} onClick={() => addFeature(chip)}>{sel ? "✓ " : ""}{chip}</button>;
            })}
          </div>
        </label>

        <ImageUploader
          value={form.image_urls_raw}
          onChange={(val) => setForm({ ...form, image_urls_raw: val })}
          label="Resimler (dosyadan yükle veya URL ekle)"
        />
        <label className="field">
          <span>Not (opsiyonel)</span>
          <textarea name="notes" value={form.notes} onChange={onChange} rows={2} placeholder="Bu oda tipi hakkında ek bilgi..." />
        </label>
        {error && <div className="error">{error}</div>}
      </form>
    </Modal>
  );
};

// ── Edit Listing Modal ────────────────────────────────────────────────────────
const EditListingModal = ({ listing, onClose, onSaved }) => {
  const [form, setForm] = React.useState({
    region: listing.region, micro_location: listing.micro_location, concept: listing.concept,
    capacity_label: listing.capacity_label, pax: listing.pax,
    date_start: listing.date_start ? new Date(listing.date_start).toISOString().split("T")[0] : "",
    date_end: listing.date_end ? new Date(listing.date_end).toISOString().split("T")[0] : "",
    nights: listing.nights, price_min: listing.price_min,
    availability_status: listing.availability_status,
    image_urls_raw: (listing.image_urls || []).join(", "),
    features_raw: (listing.features || []).join(", "),
    notes: listing.notes || "",
    allow_cross_region: listing.allow_cross_region || false,
  });
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const addFeature = (chip) => {
    const current = form.features_raw ? form.features_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
    if (!current.includes(chip)) {
      setForm({ ...form, features_raw: [...current, chip].join(", ") });
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const image_urls = form.image_urls_raw ? form.image_urls_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
      const features = form.features_raw ? form.features_raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
      await axios.put(`/listings/${listing.id}`, {
        region: form.region, micro_location: form.micro_location, concept: form.concept,
        capacity_label: form.capacity_label, pax: Number(form.pax),
        date_start: new Date(form.date_start).toISOString(),
        date_end: new Date(form.date_end).toISOString(),
        nights: Number(form.nights),
        price_min: Number(form.price_min), price_max: Number(form.price_min),
        availability_status: form.availability_status,
        image_urls, features, notes: form.notes,
        allow_cross_region: form.allow_cross_region,
      });
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || "Güncelleme başarısız.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={true} onClose={onClose} title="✏️ İlanı Düzenle" size="lg"
      footer={
        <>
          <button className="btn-ghost" onClick={onClose}>İptal</button>
          <button className="btn-primary" onClick={handleSave} disabled={loading}>
            {loading ? <><span className="loading-spin" /> Kaydediliyor...</> : "Kaydet"}
          </button>
        </>
      }
    >
      <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
        <div className="grid-2">
          <label className="field">
            <span>Bölge</span>
            <select name="region" value={form.region} onChange={onChange}>
              <option value="Sapanca">Sapanca</option>
              <option value="Kartepe">Kartepe</option>
              <option value="Abant">Abant</option>
              <option value="Ayder">Ayder</option>
              <option value="Kas">Kaş</option>
              <option value="Alacati">Alaçatı</option>
            </select>
          </label>
          <label className="field">
            <span>Mikro Lokasyon</span>
            <input name="micro_location" value={form.micro_location} onChange={onChange} required />
          </label>
        </div>
        <div className="grid-2">
          <label className="field">
            <span>Konsept</span>
            <input name="concept" value={form.concept} onChange={onChange} required />
          </label>
          <label className="field">
            <span>Durum</span>
            <select name="availability_status" value={form.availability_status} onChange={onChange}>
              <option value="available">Müsait</option>
              <option value="limited">Sınırlı</option>
              <option value="alternative">Alternatif</option>
            </select>
          </label>
        </div>
        <div className="grid-3">
          <label className="field">
            <span>Kapasite</span>
            <input name="capacity_label" value={form.capacity_label} onChange={onChange} />
          </label>
          <label className="field">
            <span>Kişi Sayısı</span>
            <input name="pax" type="number" value={form.pax} onChange={onChange} />
          </label>
          <label className="field">
            <span>Fiyat TL/gece</span>
            <input name="price_min" type="number" value={form.price_min} onChange={onChange} />
          </label>
        </div>
        <div className="grid-3">
          <label className="field">
            <span>Başlangıç</span>
            <input name="date_start" type="date" value={form.date_start} onChange={onChange} required />
          </label>
          <label className="field">
            <span>Bitiş</span>
            <input name="date_end" type="date" value={form.date_end} onChange={onChange} required />
          </label>
          <label className="field">
            <span>Gece</span>
            <input name="nights" type="number" value={form.nights} onChange={onChange} />
          </label>
        </div>
        <ImageUploader
          value={form.image_urls_raw}
          onChange={(val) => setForm({ ...form, image_urls_raw: val })}
          label="Resimler (dosyadan yükle veya URL ekle)"
        />
        <label className="field">
          <span>Özellikler</span>
          <textarea name="features_raw" value={form.features_raw} onChange={onChange} rows={2} />
          <div style={{ marginTop: "0.4rem" }}>
            {FEATURES_LIST.slice(0, 8).map((chip) => {
              const sel = form.features_raw.split(",").map((s) => s.trim()).includes(chip);
              return (
                <button key={chip} type="button" className={`feature-chip ${sel ? "selected" : ""}`} onClick={() => addFeature(chip)}>
                  {sel ? "✓ " : ""}{chip}
                </button>
              );
            })}
          </div>
        </label>
        <label className="field">
          <span>Not</span>
          <textarea name="notes" value={form.notes} onChange={onChange} rows={2} />
        </label>
        {error && <div className="error">{error}</div>}
      </form>
    </Modal>
  );
};

export default AvailabilityPage;
