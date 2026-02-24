import React from "react";
import { Link } from "react-router-dom";
import axios from "@/utils/api";

const RegisterPage = () => {
  const [form, setForm] = React.useState({
    name: "", region: "Sapanca", micro_location: "", concept: "",
    address: "", phone: "", whatsapp: "", website: "", contact_person: "",
    email: "", password: "",
  });
  const [documents, setDocuments] = React.useState([]); // [{filename, original}]
  const [docUploading, setDocUploading] = React.useState(false);
  const [docError, setDocError] = React.useState("");
  const fileInputRef = React.useRef(null);
  const [error, setError] = React.useState("");
  const [success, setSuccess] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleDocUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setDocUploading(true); setDocError("");
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        const res = await axios.post("/auth/register-upload", fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        setDocuments((prev) => [...prev, { filename: res.data.filename, original: res.data.original }]);
      }
    } catch (err) {
      setDocError(err.response?.data?.detail || "Belge yüklenemedi. PDF, JPG veya PNG olmalıdır.");
    } finally {
      setDocUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removeDoc = (idx) => setDocuments((prev) => prev.filter((_, i) => i !== idx));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (documents.length === 0) {
      setError("Lütfen en az bir konaklama belgesi yükleyin (işletme belgesi, vergi levhası vb.)");
      return;
    }
    setLoading(true);
    try {
      await axios.post("/auth/register", {
        ...form,
        documents: documents.map((d) => d.filename),
      });
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Kayıt başarısız. Bilgileri kontrol edin.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-layout">
        <div className="auth-panel" style={{ textAlign: "center", maxWidth: 520 }}>
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>⏳</div>
          <h2 style={{ color: "#1a3a2a", marginBottom: "0.75rem" }}>Başvurunuz Alındı!</h2>
          <div style={{ background: "#fef9c3", border: "1px solid #fde68a", borderRadius: "0.75rem", padding: "1rem 1.25rem", marginBottom: "1.5rem", textAlign: "left" }}>
            <p style={{ color: "#713f12", fontSize: "0.9rem", margin: "0 0 0.5rem", fontWeight: 600 }}>
              📋 Belgeleriniz inceleniyor
            </p>
            <p style={{ color: "#92400e", fontSize: "0.85rem", margin: 0, lineHeight: 1.6 }}>
              Yüklediğiniz belgeler platform yöneticisi tarafından incelenecektir.
              Onaylandıktan sonra giriş yapabilirsiniz. Bu süreç genellikle 1 iş günü içinde tamamlanır.
            </p>
          </div>
          <p style={{ color: "#6b7c93", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
            Onay durumunuz için kayıt sırasında kullandığınız e-posta adresini kontrol edebilirsiniz.
          </p>
          <Link to="/login" className="btn-secondary">← Giriş Sayfasına Dön</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-layout">
      <div className="auth-panel" style={{ maxWidth: 660 }}>
        <div className="auth-logo">
          <div className="auth-logo-icon">🏨</div>
          <span style={{ fontWeight: 700, fontSize: "1.1rem", color: "#1a3a2a" }}>CapX</span>
        </div>
        <h1 className="auth-title">Otel Üyelik Başvurusu</h1>
        <p className="auth-subtitle">
          Bilgilerinizi ve işletme belgenizi eksiksiz doldurun. Yönetici onayı sonrası platforma erişim sağlanacaktır.
        </p>
        <form onSubmit={handleSubmit} className="auth-form" data-testid="register-form">
          <div className="grid-2">
            <label className="field">
              <span>Otel / İşletme Adı</span>
              <input name="name" value={form.name} onChange={onChange} placeholder="Örn: Sapanca Bungalov" required />
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
              <input name="micro_location" value={form.micro_location} onChange={onChange} placeholder="Örn: Sapanca Gölü kıyısı" required />
            </label>
            <label className="field">
              <span>Konsept</span>
              <input name="concept" value={form.concept} onChange={onChange} placeholder="Örn: Bungalov, Butik, Resort" required />
            </label>
          </div>
          <label className="field">
            <span>Adres</span>
            <input name="address" value={form.address} onChange={onChange} required />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Telefon</span>
              <input name="phone" value={form.phone} onChange={onChange} placeholder="+90 5xx xxx xx xx" required />
            </label>
            <label className="field">
              <span>WhatsApp</span>
              <input name="whatsapp" value={form.whatsapp} onChange={onChange} placeholder="+90 5xx xxx xx xx" />
            </label>
          </div>
          <div className="grid-2">
            <label className="field">
              <span>Web Sitesi</span>
              <input name="website" value={form.website} onChange={onChange} placeholder="https://..." />
            </label>
            <label className="field">
              <span>İrtibat Kişisi</span>
              <input name="contact_person" value={form.contact_person} onChange={onChange} placeholder="Ad Soyad" />
            </label>
          </div>
          <div className="grid-2">
            <label className="field">
              <span>E-posta</span>
              <input type="email" name="email" value={form.email} onChange={onChange} required />
            </label>
            <label className="field">
              <span>Şifre</span>
              <input type="password" name="password" value={form.password} onChange={onChange} minLength={6} required />
            </label>
          </div>

          {/* Belge Yükleme */}
          <div style={{ background: "#f8fafc", border: "1.5px dashed #b2dfd0", borderRadius: "0.75rem", padding: "1.1rem" }}>
            <div style={{ fontWeight: 700, color: "#1a3a2a", marginBottom: "0.35rem", fontSize: "0.9rem" }}>
              📄 Konaklama / İşletme Belgesi <span style={{ color: "#dc2626" }}>*</span>
            </div>
            <div style={{ fontSize: "0.82rem", color: "#6b7c93", marginBottom: "0.75rem" }}>
              İşletme ruhsatı, turizm belgesi veya vergi levhası yükleyin. PDF, JPG, PNG — max 20 MB.
            </div>

            {documents.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginBottom: "0.75rem" }}>
                {documents.map((doc, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem", background: "#f0f9f5", borderRadius: "0.5rem", padding: "0.4rem 0.75rem", border: "1px solid #b2dfd0" }}>
                    <span style={{ fontSize: "1rem" }}>{doc.original?.endsWith(".pdf") ? "📄" : "🖼️"}</span>
                    <span style={{ flex: 1, fontSize: "0.85rem", color: "#1a3a2a", fontWeight: 500 }}>{doc.original}</span>
                    <button type="button" onClick={() => removeDoc(i)} style={{ background: "none", border: "none", cursor: "pointer", color: "#dc2626", fontSize: "1rem" }}>✕</button>
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={docUploading}
              >
                {docUploading ? <><span className="loading-spin" style={{ width: 13, height: 13, borderWidth: 2 }} /> Yükleniyor...</> : "📁 Belge Seç"}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,image/jpeg,image/png,image/webp"
                style={{ display: "none" }}
                onChange={handleDocUpload}
              />
              <span style={{ fontSize: "0.78rem", color: "#9ca3af" }}>{documents.length > 0 ? `${documents.length} belge yüklendi` : "Henüz belge yüklenmedi"}</span>
            </div>
            {docError && <div className="error" style={{ marginTop: "0.5rem", fontSize: "0.82rem" }}>{docError}</div>}
          </div>

          {error && <div className="error">{error}</div>}
          <button className="btn-primary w-full" type="submit" disabled={loading} data-testid="register-submit">
            {loading ? <><span className="loading-spin" /> Gönderiliyor...</> : "📩 Başvuruyu Gönder"}
          </button>
        </form>
        <div className="auth-links">
          Hesabınız var mı? <Link to="/login">Giriş Yap</Link>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
