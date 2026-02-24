import React from "react";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";

const GoogleSheetsTab = () => {
  const [config, setConfig] = React.useState(null);
  const [form, setForm] = React.useState({ client_id: "", client_secret: "", spreadsheet_id: "" });
  const [saving, setSaving] = React.useState(false);
  const [syncing, setSyncing] = React.useState("");
  const [msg, setMsg] = React.useState("");
  const [err, setErr] = React.useState("");

  const loadConfig = async () => {
    try {
      const res = await axios.get("/sheets/config");
      setConfig(res.data);
      setForm({
        client_id: res.data.client_id_full || "",
        client_secret: "",  // güvenlik: tekrar girmelerini iste
        spreadsheet_id: res.data.spreadsheet_id || "",
      });
    } catch { setConfig(null); }
  };

  React.useEffect(() => { loadConfig(); }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setErr(""); setMsg(""); setSaving(true);
    try {
      const payload = { client_id: form.client_id };
      if (form.client_secret) payload.client_secret = form.client_secret;
      if (form.spreadsheet_id) payload.spreadsheet_id = form.spreadsheet_id;
      await axios.post("/sheets/config", payload);
      setMsg("✅ Bilgiler kaydedildi.");
      await loadConfig();
    } catch (e) {
      setErr(e.response?.data?.detail || "Kaydetme başarısız.");
    } finally { setSaving(false); }
  };

  const handleConnect = async () => {
    setErr(""); setMsg("");
    try {
      const res = await axios.get("/oauth/sheets/login");
      // Yeni sekmede aç
      const popup = window.open(res.data.auth_url, "_blank", "noopener,noreferrer,width=600,height=700");
      // Sekme kapandığında bağlantı durumunu yenile
      const check = setInterval(async () => {
        if (popup && popup.closed) {
          clearInterval(check);
          await loadConfig();
          setMsg("Bağlantı durumu güncellendi. Yenileniyor...");
        }
      }, 1000);
      // 5 dakika sonra polling'i durdur
      setTimeout(() => clearInterval(check), 300000);
    } catch (e) {
      setErr(e.response?.data?.detail || "Bağlantı başlatılamadı. Önce Client ID ve Secret kaydedin.");
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm("Google Sheets bağlantısını kesmek istediğinize emin misiniz?")) return;
    try {
      await axios.delete("/sheets/disconnect");
      setMsg("Bağlantı kesildi.");
      await loadConfig();
    } catch (e) {
      setErr(e.response?.data?.detail || "Bağlantı kesilemedi.");
    }
  };

  const handleSync = async (type) => {
    setErr(""); setMsg(""); setSyncing(type);
    try {
      const res = await axios.post(`/sheets/sync/${type}`);
      setMsg(`${res.data.message} `);
      if (res.data.spreadsheet_url) {
        setMsg(`${res.data.message} → `);
        window._sheetsUrl = res.data.spreadsheet_url;
      }
      await loadConfig();
    } catch (e) {
      setErr(e.response?.data?.detail || "Senkronizasyon başarısız.");
    } finally { setSyncing(""); }
  };

  const REDIRECT_URI = `${process.env.REACT_APP_BACKEND_URL}/api/oauth/sheets/callback`;

  return (
    <div className="profile-form-card" style={{ gap: "1.5rem" }}>

      {/* Nasıl kurulur */}
      <div style={{ background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: "0.75rem", padding: "1rem" }}>
        <div style={{ fontWeight: 700, color: "#0c4a6e", marginBottom: "0.75rem", fontSize: "0.95rem" }}>
          📋 Nasıl Kurulur? (3 Adım)
        </div>
        <ol style={{ margin: 0, paddingLeft: "1.25rem", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.85rem", color: "#0c4a6e" }}>
          <li>
            <a href="https://console.cloud.google.com" target="_blank" rel="noopener noreferrer" style={{ color: "#2563eb", fontWeight: 600 }}>
              Google Cloud Console
            </a>
            {" "}→ Yeni Proje oluşturun → <strong>Google Sheets API</strong>'yi etkinleştirin
          </li>
          <li>
            <strong>APIs &amp; Services → Credentials → OAuth 2.0 Client ID</strong> (Web Application tipinde) oluşturun.
            <br />
            <strong>Authorized redirect URI</strong> olarak aşağıdaki adresi ekleyin:
            <div style={{ background: "#fff", border: "1px solid #bae6fd", borderRadius: "0.4rem", padding: "0.4rem 0.65rem", marginTop: "0.3rem", fontFamily: "monospace", fontSize: "0.8rem", wordBreak: "break-all", userSelect: "all", cursor: "copy" }}
              title="Kopyalamak için tıklayın"
              onClick={() => { navigator.clipboard.writeText(REDIRECT_URI); }}
            >
              {REDIRECT_URI}
            </div>
            <div style={{ fontSize: "0.75rem", color: "#6b7c93", marginTop: "0.25rem" }}>
              📋 Yukarıdaki kutuya tıklayarak kopyalayabilirsiniz. Bu adres Google Console'a <strong>tam olarak</strong> girilmelidir.
            </div>
          </li>
          <li>Oluşturulan <strong>Client ID</strong> ve <strong>Client Secret</strong>'ı aşağıya girin → <strong>Kaydet</strong> → <strong>Google ile Bağlan</strong></li>
        </ol>
        <div style={{ marginTop: "0.75rem", background: "#fef3c7", border: "1px solid #fde68a", borderRadius: "0.5rem", padding: "0.6rem 0.85rem", fontSize: "0.8rem", color: "#713f12" }}>
          ⚠️ <strong>Erişim engellendi / invalid_client hatası alıyorsanız:</strong> Google Console'da Authorized redirect URI'nin yukarıdaki adresle <strong>birebir aynı</strong> olduğunu kontrol edin. Tek karakter farkı bile hata verir.
        </div>
      </div>

      {/* Bağlantı durumu */}
      {config?.connected && (
        <div style={{ background: "#f0f9f5", border: "1px solid #b2dfd0", borderRadius: "0.75rem", padding: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
          <div>
            <div style={{ fontWeight: 700, color: "#166534", fontSize: "0.95rem" }}>✅ Google Sheets Bağlı</div>
            <div style={{ fontSize: "0.85rem", color: "#4a5568" }}>
              {config.google_email && <span>📧 {config.google_email}</span>}
              {config.connected_at && <span style={{ marginLeft: "1rem" }}>🕐 {new Date(config.connected_at).toLocaleString("tr-TR")}</span>}
            </div>
            {config.spreadsheet_id && (
              <a
                href={`https://docs.google.com/spreadsheets/d/${config.spreadsheet_id}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: "0.82rem", color: "#2e6b57", fontWeight: 600, marginTop: "0.25rem", display: "inline-block" }}
              >
                📊 Google Sheets'i Aç →
              </a>
            )}
          </div>
          <button className="btn-danger btn-sm" onClick={handleDisconnect}>Bağlantıyı Kes</button>
        </div>
      )}

      {/* Kimlik Bilgileri Formu */}
      <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
        <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "#374151" }}>🔑 Google OAuth Kimlik Bilgileri</div>
        <label className="field">
          <span>Client ID</span>
          <input
            value={form.client_id}
            onChange={(e) => setForm({ ...form, client_id: e.target.value })}
            placeholder="xxx.apps.googleusercontent.com"
            required
          />
        </label>
        <label className="field">
          <span>Client Secret {config?.client_secret_saved && <span style={{ color: "#6b7c93", fontWeight: 400 }}>(kayıtlı — değiştirmek için girin)</span>}</span>
          <input
            type="password"
            value={form.client_secret}
            onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
            placeholder={config?.client_secret_saved ? "••••••••• (kayıtlı)" : "GOCSPX-..."}
            required={!config?.client_secret_saved}
          />
        </label>
        <label className="field">
          <span>Mevcut Spreadsheet ID <span style={{ color: "#6b7c93", fontWeight: 400 }}>(opsiyonel — boş bırakırsanız otomatik oluşturulur)</span></span>
          <input
            value={form.spreadsheet_id}
            onChange={(e) => setForm({ ...form, spreadsheet_id: e.target.value })}
            placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
          />
          <span className="field-help">Spreadsheet URL'sindeki /d/ ile /edit arasındaki ID kısmı</span>
        </label>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <button className="btn-primary" type="submit" disabled={saving}>
            {saving ? <><span className="loading-spin" /> Kaydediliyor...</> : "💾 Kaydet"}
          </button>
          {config?.client_id && !config?.connected && (
            <button type="button" className="btn-secondary" onClick={handleConnect}
              style={{ background: "#fff", border: "2px solid #4285F4", color: "#4285F4", fontWeight: 700 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" style={{ marginRight: "0.35rem" }}>
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Google ile Bağlan
            </button>
          )}
          {config?.connected && (
            <button type="button" className="btn-secondary" onClick={handleConnect}>
              🔄 Yeniden Bağlan
            </button>
          )}
        </div>
      </form>

      {msg && (
        <div className="success">
          {msg}
          {window._sheetsUrl && (
            <a href={window._sheetsUrl} target="_blank" rel="noopener noreferrer"
              style={{ marginLeft: "0.5rem", color: "#166534", fontWeight: 700, textDecoration: "underline" }}>
              Sheets'i Aç →
            </a>
          )}
        </div>
      )}
      {err && <div className="error">{err}</div>}

      {/* Senkronizasyon */}
      {config?.connected && (
        <div style={{ borderTop: "1px solid #f0f4f8", paddingTop: "1.25rem" }}>
          <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "#374151", marginBottom: "1rem" }}>
            🔄 Verileri Senkronize Et
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem" }}>

            <div style={{ background: "#f8fafc", borderRadius: "0.75rem", padding: "1rem", border: "1px solid #e2e8f0" }}>
              <div style={{ fontWeight: 600, color: "#374151", marginBottom: "0.35rem" }}>🏠 Oda Tipleri</div>
              <div style={{ fontSize: "0.8rem", color: "#6b7c93", marginBottom: "0.75rem" }}>
                Kayıtlı oda şablonlarınızı Sheets'e aktar
              </div>
              <button className="btn-secondary btn-sm w-full" onClick={() => handleSync("templates")} disabled={!!syncing}>
                {syncing === "templates" ? <><span className="loading-spin" style={{ width: 12, height: 12, borderWidth: 2 }} /> Senkronize ediliyor...</> : "📤 Senkronize Et"}
              </button>
            </div>

            <div style={{ background: "#f8fafc", borderRadius: "0.75rem", padding: "1rem", border: "1px solid #e2e8f0" }}>
              <div style={{ fontWeight: 600, color: "#374151", marginBottom: "0.35rem" }}>📅 Müsaitlikler</div>
              <div style={{ fontSize: "0.8rem", color: "#6b7c93", marginBottom: "0.75rem" }}>
                Tüm kapasite ilanlarınızı Sheets'e aktar
              </div>
              <button className="btn-secondary btn-sm w-full" onClick={() => handleSync("listings")} disabled={!!syncing}>
                {syncing === "listings" ? <><span className="loading-spin" style={{ width: 12, height: 12, borderWidth: 2 }} /> Senkronize ediliyor...</> : "📤 Senkronize Et"}
              </button>
            </div>

            <div style={{ background: "#f8fafc", borderRadius: "0.75rem", padding: "1rem", border: "1px solid #e2e8f0" }}>
              <div style={{ fontWeight: 600, color: "#374151", marginBottom: "0.35rem" }}>🤝 Eşleşmeler</div>
              <div style={{ fontSize: "0.8rem", color: "#6b7c93", marginBottom: "0.75rem" }}>
                Kabul edilen eşleşmeleri Sheets'e aktar
              </div>
              <button className="btn-secondary btn-sm w-full" onClick={() => handleSync("matches")} disabled={!!syncing}>
                {syncing === "matches" ? <><span className="loading-spin" style={{ width: 12, height: 12, borderWidth: 2 }} /> Senkronize ediliyor...</> : "📤 Senkronize Et"}
              </button>
            </div>

            <div style={{ background: "#f0f9f5", borderRadius: "0.75rem", padding: "1rem", border: "1px solid #b2dfd0" }}>
              <div style={{ fontWeight: 700, color: "#166534", marginBottom: "0.35rem" }}>⚡ Tümünü Senkronize Et</div>
              <div style={{ fontSize: "0.8rem", color: "#4a5568", marginBottom: "0.75rem" }}>
                Oda tipleri + müsaitlikler + eşleşmeler
              </div>
              <button className="btn-primary btn-sm w-full" onClick={() => handleSync("all")} disabled={!!syncing}>
                {syncing === "all" ? <><span className="loading-spin" style={{ width: 12, height: 12, borderWidth: 2 }} /> Senkronize ediliyor...</> : "🚀 Tümünü Senkronize Et"}
              </button>
            </div>

          </div>

          <div className="section-note" style={{ marginTop: "1rem" }}>
            📌 Senkronizasyon tek yönlüdür: platform → Google Sheets. Her senkronizasyonda ilgili sayfa tamamen yenilenir.
            Spreadsheet otomatik oluşturulur ve "Oda Tipleri", "Müsaitlikler", "Eşleşmeler" adlı 3 sekme içerir.
          </div>
        </div>
      )}
    </div>
  );
};

// ── Profile Page ──────────────────────────────────────────────────────────────
const ProfilePage = () => {
  const { hotel, reload } = useAuth();
  const location = useLocation();
  const [tab, setTab] = React.useState(
    new URLSearchParams(location.search).get("sheets") === "connected" ? "sheets" : "profile"
  );
  const [form, setForm] = React.useState({
    name: hotel?.name || "", region: hotel?.region || "Sapanca",
    micro_location: hotel?.micro_location || "", concept: hotel?.concept || "",
    address: hotel?.address || "", phone: hotel?.phone || "",
    whatsapp: hotel?.whatsapp || "", website: hotel?.website || "",
    contact_person: hotel?.contact_person || "",
  });
  const [pwForm, setPwForm] = React.useState({ current_password: "", new_password: "", confirm: "" });
  const [loading, setLoading] = React.useState(false);
  const [pwLoading, setPwLoading] = React.useState(false);
  const [success, setSuccess] = React.useState(
    new URLSearchParams(location.search).get("sheets") === "connected"
      ? "✅ Google Sheets bağlantısı başarıyla kuruldu!"
      : ""
  );
  const [error, setError] = React.useState("");

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleProfile = async (e) => {
    e.preventDefault();
    setError(""); setSuccess(""); setLoading(true);
    try {
      await axios.put("/hotels/me", form);
      await reload();
      setSuccess("✅ Profil güncellendi!");
    } catch (err) {
      setError(err.response?.data?.detail || "Güncelleme başarısız.");
    } finally {
      setLoading(false);
    }
  };

  const handlePassword = async (e) => {
    e.preventDefault();
    setError(""); setSuccess("");
    if (pwForm.new_password !== pwForm.confirm) {
      setError("Yeni şifreler eşleşmiyor.");
      return;
    }
    setPwLoading(true);
    try {
      await axios.post("/auth/change-password", {
        current_password: pwForm.current_password,
        new_password: pwForm.new_password,
      });
      setSuccess("✅ Şifre değiştirildi!");
      setPwForm({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      setError(err.response?.data?.detail || "Şifre değiştirme başarısız.");
    } finally {
      setPwLoading(false);
    }
  };

  const initials = hotel?.name ? hotel.name.slice(0, 2).toUpperCase() : "OT";

  return (
    <Layout>
      <h1 className="page-title">Profilim</h1>

      <div className="profile-grid">
        <div className="profile-card">
          <div className="profile-avatar">{initials}</div>
          <div className="profile-name">{hotel?.name}</div>
          <div className="profile-email">{hotel?.email}</div>
          <div style={{ marginTop: "0.5rem" }}>
            <span className="badge-region">{hotel?.region}</span>
          </div>
          {hotel?.is_admin && (
            <div style={{ marginTop: "0.5rem" }}>
              <span className="admin-badge">⚙️ Platform Yöneticisi</span>
            </div>
          )}
          <div style={{ marginTop: "1.25rem", borderTop: "1px solid #f0f4f8", paddingTop: "1rem", display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.85rem", textAlign: "left" }}>
            {hotel?.phone && <div>📞 {hotel.phone}</div>}
            {hotel?.whatsapp && <div>💬 {hotel.whatsapp}</div>}
            {hotel?.website && <div>🌐 <a href={hotel.website} target="_blank" rel="noopener noreferrer" style={{ color: "#2e6b57" }}>{hotel.website}</a></div>}
            {hotel?.contact_person && <div>👤 {hotel.contact_person}</div>}
          </div>
        </div>

        <div>
          <div className="tabs">
            <div className={`tab ${tab === "profile" ? "active" : ""}`} onClick={() => setTab("profile")}>
              Profil Bilgileri
            </div>
            <div className={`tab ${tab === "password" ? "active" : ""}`} onClick={() => setTab("password")}>
              Şifre Değiştir
            </div>
            <div className={`tab ${tab === "sheets" ? "active" : ""}`} onClick={() => setTab("sheets")}>
              📊 Google Sheets
            </div>
            <div className={`tab ${tab === "kvkk" ? "active" : ""}`} onClick={() => setTab("kvkk")}>
              🔒 KVKK
            </div>
          </div>

          {success && <div className="success mb-2">{success}</div>}
          {error && <div className="error mb-2">{error}</div>}

          {tab === "profile" && (
            <form onSubmit={handleProfile} className="profile-form-card">
              <div className="grid-2">
                <label className="field">
                  <span>Otel Adı</span>
                  <input name="name" value={form.name} onChange={onChange} required />
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
              </div>
              <div className="grid-2">
                <label className="field">
                  <span>Mikro Lokasyon</span>
                  <input name="micro_location" value={form.micro_location} onChange={onChange} />
                </label>
                <label className="field">
                  <span>Konsept</span>
                  <input name="concept" value={form.concept} onChange={onChange} />
                </label>
              </div>
              <label className="field">
                <span>Adres</span>
                <input name="address" value={form.address} onChange={onChange} />
              </label>
              <div className="grid-2">
                <label className="field">
                  <span>Telefon</span>
                  <input name="phone" value={form.phone} onChange={onChange} />
                </label>
                <label className="field">
                  <span>WhatsApp</span>
                  <input name="whatsapp" value={form.whatsapp} onChange={onChange} />
                </label>
              </div>
              <div className="grid-2">
                <label className="field">
                  <span>Web Sitesi</span>
                  <input name="website" value={form.website} onChange={onChange} />
                </label>
                <label className="field">
                  <span>İrtibat Kişisi</span>
                  <input name="contact_person" value={form.contact_person} onChange={onChange} />
                </label>
              </div>
              <button className="btn-primary" type="submit" disabled={loading}>
                {loading ? <><span className="loading-spin" /> Kaydediliyor...</> : "💾 Kaydet"}
              </button>
            </form>
          )}

          {tab === "password" && (
            <form onSubmit={handlePassword} className="profile-form-card">
              <label className="field">
                <span>Mevcut Şifre</span>
                <input
                  type="password"
                  value={pwForm.current_password}
                  onChange={(e) => setPwForm({ ...pwForm, current_password: e.target.value })}
                  required
                />
              </label>
              <label className="field">
                <span>Yeni Şifre</span>
                <input
                  type="password"
                  value={pwForm.new_password}
                  onChange={(e) => setPwForm({ ...pwForm, new_password: e.target.value })}
                  minLength={6}
                  required
                />
              </label>
              <label className="field">
                <span>Yeni Şifre (Tekrar)</span>
                <input
                  type="password"
                  value={pwForm.confirm}
                  onChange={(e) => setPwForm({ ...pwForm, confirm: e.target.value })}
                  required
                />
              </label>
              <button className="btn-primary" type="submit" disabled={pwLoading}>
                {pwLoading ? <><span className="loading-spin" /> Değiştiriliyor...</> : "🔐 Şifreyi Değiştir"}
              </button>
            </form>
          )}

          {tab === "sheets" && <GoogleSheetsTab />}

          {tab === "kvkk" && (
            <div className="card" style={{ padding: "1.5rem" }}>
              <h3>🔒 KVKK - Kişisel Verilerin Korunması</h3>
              <p style={{ color: "#6b7c93", margin: "1rem 0", fontSize: "0.9rem" }}>
                6698 sayılı Kişisel Verilerin Korunması Kanunu kapsamında, kişisel verilerinizi görüntüleyebilir,
                dışa aktarabilir veya hesap silme talebinde bulunabilirsiniz.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div className="card" style={{ background: "#f0fdf4", padding: "1rem" }}>
                  <h4>📥 Verilerimi Dışa Aktar</h4>
                  <p style={{ fontSize: "0.85rem", color: "#6b7c93", margin: "0.5rem 0" }}>Tüm kişisel verilerinizi JSON formatında indirin.</p>
                  <button className="btn-primary btn-sm" onClick={async () => {
                    try {
                      const res = await axios.get("/kvkk/export");
                      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url; a.download = `kvkk-export-${new Date().toISOString().slice(0, 10)}.json`;
                      a.click(); URL.revokeObjectURL(url);
                    } catch { alert("Dışa aktarma başarısız"); }
                  }}>📥 Dışa Aktar</button>
                </div>
                <div className="card" style={{ background: "#fef2f2", padding: "1rem" }}>
                  <h4>🗑️ Hesap Silme Talebi</h4>
                  <p style={{ fontSize: "0.85rem", color: "#6b7c93", margin: "0.5rem 0" }}>Hesabınızın ve tüm verilerinizin silinmesini talep edin. Bu işlem 30 gün içinde gerçekleştirilir.</p>
                  <button className="btn-ghost btn-sm" style={{ color: "#ef4444", borderColor: "#ef4444" }} onClick={async () => {
                    if (!window.confirm("Hesabınızın silinmesini talep etmek istediğinize emin misiniz? Bu işlem geri alınamaz.")) return;
                    try {
                      const res = await axios.post("/kvkk/delete-request");
                      alert(res.data.message);
                    } catch (e) { alert(e.response?.data?.detail || "Hata"); }
                  }}>🗑️ Silme Talebi Oluştur</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default ProfilePage;
