import React from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useParams,
  Link,
  useLocation,
} from "react-router-dom";
import axios from "axios";
import "@/App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Auth utils
const getToken = () => localStorage.getItem("token");
const setToken = (t) => localStorage.setItem("token", t || "");
const clearToken = () => localStorage.removeItem("token");

axios.defaults.baseURL = API;
axios.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Auth Context ─────────────────────────────────────────────────────────────
const AuthContext = React.createContext(null);

const AuthProvider = ({ children }) => {
  const [hotel, setHotel] = React.useState(null);

  const loadMe = async () => {
    if (!getToken()) return;
    try {
      const res = await axios.get("/auth/me");
      setHotel(res.data);
    } catch {
      clearToken();
      setHotel(null);
    }
  };

  React.useEffect(() => { loadMe(); }, []);

  const login = async (email, password) => {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    const res = await axios.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    setToken(res.data.access_token);
    await loadMe();
  };

  const logout = () => { clearToken(); setHotel(null); };

  return (
    <AuthContext.Provider value={{ hotel, login, logout, reload: loadMe }}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuth = () => React.useContext(AuthContext);

const ProtectedRoute = ({ children }) => {
  const { hotel } = useAuth();
  if (!getToken()) return <Navigate to="/login" replace />;
  if (!hotel) return <div className="page-center"><span className="loading-spin" /></div>;
  return children;
};

// ── Small reusable helpers ────────────────────────────────────────────────────
const Modal = ({ open, onClose, title, children, footer, size }) => {
  if (!open) return null;
  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal-box ${size === "lg" ? "modal-box-lg" : size === "sm" ? "modal-box-sm" : ""}`}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="btn-icon" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
};

// ── Image Uploader Component ──────────────────────────────────────────────────
// Hem URL girişi hem dosya yüklemeyi destekler
const ImageUploader = ({ value, onChange, label = "Resimler" }) => {
  const [uploading, setUploading] = React.useState(false);
  const [uploadError, setUploadError] = React.useState("");
  const [urlInput, setUrlInput] = React.useState("");
  const fileInputRef = React.useRef(null);

  // value → string (virgülle ayrılmış URL'ler)
  const urls = value ? value.split(",").map((s) => s.trim()).filter(Boolean) : [];

  const addUrl = (url) => {
    if (!url.trim()) return;
    if (urls.includes(url.trim())) return;
    onChange([...urls, url.trim()].join(", "));
    setUrlInput("");
  };

  const removeUrl = (idx) => {
    const next = urls.filter((_, i) => i !== idx);
    onChange(next.join(", "));
  };

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setUploading(true);
    setUploadError("");
    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        const res = await axios.post("/upload-image", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const fullUrl = `${process.env.REACT_APP_BACKEND_URL}/api/files/${res.data.filename}`;
        if (!urls.includes(fullUrl)) {
          urls.push(fullUrl);
        }
      }
      onChange(urls.join(", "));
    } catch (err) {
      setUploadError(err.response?.data?.detail || "Yükleme başarısız. Dosya JPG/PNG/WEBP olmalı, max 10 MB.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#374151", textTransform: "uppercase", letterSpacing: "0.03em" }}>
        {label}
      </span>

      {/* Önizleme */}
      {urls.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          {urls.map((url, i) => (
            <div key={i} style={{ position: "relative", width: 80, height: 64 }}>
              <img
                src={url}
                alt={`Resim ${i + 1}`}
                style={{ width: 80, height: 64, objectFit: "cover", borderRadius: "0.4rem", border: "1px solid #e2e8f0" }}
                onError={(e) => { e.target.style.display = "none"; }}
              />
              <button
                type="button"
                onClick={() => removeUrl(i)}
                style={{
                  position: "absolute", top: -6, right: -6,
                  width: 18, height: 18, borderRadius: "50%",
                  background: "#dc2626", color: "#fff",
                  border: "none", cursor: "pointer",
                  fontSize: "0.65rem", lineHeight: 1,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Dosya yükle butonu */}
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}
        >
          {uploading ? <><span className="loading-spin" style={{ width: 14, height: 14, borderWidth: 2 }} /> Yükleniyor...</> : "📁 Dosyadan Yükle"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp,image/gif"
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>JPG, PNG, WEBP — max 10 MB</span>
      </div>

      {/* URL ile ekle */}
      <div style={{ display: "flex", gap: "0.4rem" }}>
        <input
          type="url"
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addUrl(urlInput))}
          placeholder="veya URL yapıştırın: https://..."
          style={{
            flex: 1, borderRadius: "0.5rem", border: "1.5px solid #e2e8f0",
            padding: "0.5rem 0.75rem", fontSize: "0.875rem", background: "#fafafa",
          }}
        />
        <button type="button" className="btn-secondary btn-sm" onClick={() => addUrl(urlInput)}>
          Ekle
        </button>
      </div>

      {uploadError && <div className="error" style={{ fontSize: "0.8rem" }}>{uploadError}</div>}
      <div className="field-help">⚠️ Logo, tabela veya iletişim bilgisi görünen görseller kullanmayın.</div>
    </div>
  );
};

const ConfirmDialog = ({ open, title, message, onConfirm, onCancel, confirmLabel = "Evet", danger = true }) => {
  if (!open) return null;
  return (
    <div className="modal-overlay">
      <div className="confirm-dialog">
        <div className="confirm-dialog-title">{title}</div>
        <div className="confirm-dialog-sub">{message}</div>
        <div className="confirm-dialog-actions">
          <button className="btn-ghost" onClick={onCancel}>İptal</button>
          <button
            className={danger ? "btn-danger" : "btn-primary"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

const statusLabel = (s) => {
  const map = {
    pending: "Beklemede",
    accepted: "Kabul",
    rejected: "Red",
    alternative_offered: "Alternatif Sunuldu",
    cancelled: "İptal",
    available: "Müsait",
    limited: "Sınırlı",
    alternative: "Alternatif",
  };
  return map[s] || s;
};

const FEATURES_LIST = [
  "Jakuzili","Şömine","Isıtmalı soba","Göl manzarası","Dağ manzarası",
  "Özel bahçe","Havuz","Isıtmalı havuz","Barbekü alanı",
  "Evcil hayvan uygun","Otopark","Bebek karyolası","Engelli erişim","Spa",
  "Özel teras","Balkon","Mutfaklı","Film köşesi","Bisiklet kiralama",
];

const ROOM_TYPES = [
  { value: "standart", label: "🛏 Standart Oda" },
  { value: "suite",    label: "🌟 Süit" },
  { value: "bungalov", label: "🏡 Bungalov" },
  { value: "villa",    label: "🏰 Villa" },
  { value: "apart",    label: "🏢 Apart" },
  { value: "dag_evi",  label: "⛰ Dağ Evi" },
  { value: "treehouse",label: "🌳 Ağaç Evi" },
  { value: "konteyner",label: "📦 Konteyner Oda" },
  { value: "cift_oda", label: "👫 Çift Kişilik Oda" },
  { value: "aile_oda", label: "👨‍👩‍👧 Aile Odası" },
];

const GUEST_RESTRICTIONS_LIST = [
  "Sadece çift",
  "Sadece aile",
  "18 yaş üstü",
  "Evcil hayvan kabul edilmez",
  "Çocuk kabul edilmez",
  "Grup kabul edilmez",
  "Sigara içilmez",
  "Bekâr grubu kabul edilmez",
];

const roomTypeLabel = (val) => {
  const found = ROOM_TYPES.find((r) => r.value === val);
  return found ? found.label : val;
};

// ── Layout ────────────────────────────────────────────────────────────────────
const Layout = ({ children }) => {
  const { hotel, logout } = useAuth();
  const location = useLocation();
  const isActive = (path) => location.pathname.startsWith(path) ? "active" : "";
  const [unreadCount, setUnreadCount] = React.useState(0);

  React.useEffect(() => {
    const loadUnread = async () => {
      try {
        const res = await axios.get("/notifications/unread-count");
        setUnreadCount(res.data.count);
      } catch {}
    };
    loadUnread();
    const interval = setInterval(loadUnread, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-brand">
          <div className="shell-brand-icon">🏨</div>
          CapX Platform
        </div>
        <div className="shell-right">
          <Link to="/notifications" className="notification-bell" title="Bildirimler">
            🔔
            {unreadCount > 0 && <span className="notification-badge">{unreadCount > 9 ? "9+" : unreadCount}</span>}
          </Link>
          <span className="shell-user">{hotel?.name}</span>
          {hotel?.is_admin && (
            <span className="admin-badge">⚙️ Admin</span>
          )}
          <button className="btn-ghost btn-sm" onClick={logout} data-testid="logout-button">
            Çıkış
          </button>
        </div>
      </header>

      <div className="shell-main">
        <nav className="shell-nav">
          <div className="shell-nav-label">Ana Menü</div>
          <Link to="/dashboard" className={isActive("/dashboard")} data-testid="nav-dashboard">
            📊 Panel
          </Link>
          <Link to="/listings" className={isActive("/listings")} data-testid="nav-listings">
            🔍 Kapasiteler
          </Link>
          <Link to="/availability" className={isActive("/availability")} data-testid="nav-availability">
            🏠 Kendi Kapasitem
          </Link>
          <Link to="/inventory" className={isActive("/inventory")} data-testid="nav-inventory">
            📦 Envanter
          </Link>
          <Link to="/requests" className={isActive("/requests")} data-testid="nav-requests">
            📋 Talepler
          </Link>
          <Link to="/matches" className={isActive("/matches")} data-testid="nav-matches">
            🤝 Eşleşmeler
          </Link>
          <div className="shell-nav-divider" />
          <div className="shell-nav-label">Finans</div>
          <Link to="/payments" className={isActive("/payments")}>
            💳 Ödemeler
          </Link>
          <Link to="/invoices" className={isActive("/invoices")}>
            🧾 Faturalar
          </Link>
          <Link to="/subscription" className={isActive("/subscription")}>
            ⭐ Abonelik
          </Link>
          <div className="shell-nav-divider" />
          <div className="shell-nav-label">Hesap</div>
          <Link to="/pricing" className={isActive("/pricing")}>
            💰 Fiyatlama
          </Link>
          <Link to="/reports" className={isActive("/reports")}>
            📈 Raporlar
          </Link>
          <Link to="/profile" className={isActive("/profile")}>
            👤 Profilim
          </Link>
          {hotel?.is_admin && (
            <>
              <div className="shell-nav-divider" />
              <div className="shell-nav-label">Yönetim</div>
              <Link to="/admin" className={isActive("/admin")}>
                ⚙️ Admin Panel
              </Link>
              <Link to="/performance" className={isActive("/performance")}>
                🚀 Performans
              </Link>
            </>
          )}
        </nav>
        <main className="shell-content">{children}</main>
      </div>
    </div>
  );
};

// ── Login Page ────────────────────────────────────────────────────────────────
const LoginPage = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      const detail = err.response?.data?.detail || "";
      if (detail.startsWith("PENDING_REVIEW:")) {
        setError("⏳ Başvurunuz henüz incelenmektedir. Onaylandıktan sonra giriş yapabilirsiniz.");
      } else if (detail.startsWith("REJECTED:")) {
        setError(detail.replace("REJECTED: ", "❌ "));
      } else {
        setError("Giriş başarısız. E-posta veya şifre hatalı.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-panel">
        <div className="auth-logo">
          <div className="auth-logo-icon">🏨</div>
          <span style={{ fontWeight: 700, fontSize: "1.1rem", color: "#1a3a2a" }}>CapX</span>
        </div>
        <h1 className="auth-title">Hoş Geldiniz</h1>
        <p className="auth-subtitle">
          Sapanca &amp; Kartepe otelleri için kapalı devre B2B kapasite paylaşım platformu.
        </p>
        <form onSubmit={handleSubmit} className="auth-form" data-testid="login-form">
          <label className="field">
            <span>E-posta</span>
            <input
              data-testid="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="otel@example.com"
              required
            />
          </label>
          <label className="field">
            <span>Şifre</span>
            <input
              data-testid="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </label>
          {error && <div className="error" data-testid="login-error">{error}</div>}
          <button
            data-testid="login-submit"
            className="btn-primary w-full"
            type="submit"
            disabled={loading}
          >
            {loading ? <><span className="loading-spin" /> Giriş yapılıyor...</> : "Giriş Yap"}
          </button>
        </form>
        <div className="auth-links">
          Hesabınız yok mu? <Link to="/register">Kayıt Ol</Link>
        </div>
      </div>
    </div>
  );
};

// ── Register Page ─────────────────────────────────────────────────────────────
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

// ── Dashboard ─────────────────────────────────────────────────────────────────
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

// ── Listings (Browse) ─────────────────────────────────────────────────────────
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
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
};

// ── Listing Detail ────────────────────────────────────────────────────────────
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

// ── Availability (My Listings) ────────────────────────────────────────────────
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

// ── Requests ──────────────────────────────────────────────────────────────────
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

// ── Matches ───────────────────────────────────────────────────────────────────
const MatchesPage = () => {
  const [matches, setMatches] = React.useState([]);
  const navigate = useNavigate();

  React.useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get("/matches");
        setMatches(res.data);
      } catch {
        setMatches([]);
      }
    };
    load();
  }, []);

  return (
    <Layout>
      <h1 className="page-title">Eşleşmeler</h1>
      {matches.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🤝</div>
          <div className="empty-state-title">Henüz eşleşme yok</div>
          <div className="empty-state-sub">Kabul edilen talepler burada görünür.</div>
        </div>
      ) : (
        <div className="matches-table-wrap">
          <table className="requests-table" data-testid="matches-table">
            <thead>
              <tr>
                <th>Referans Kodu</th>
                <th>Kabul Tarihi</th>
                <th>Hizmet Bedeli</th>
                <th>Ödeme Durumu</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m) => (
                <tr key={m.id}>
                  <td style={{ fontWeight: 700, fontFamily: "monospace", color: "#2e6b57" }}>{m.reference_code}</td>
                  <td>{m.accepted_at ? new Date(m.accepted_at).toLocaleDateString("tr-TR") : "-"}</td>
                  <td style={{ fontWeight: 600 }}>{m.fee_amount.toLocaleString("tr-TR")} TL</td>
                  <td>
                    <span className={`status-chip ${m.fee_status === "paid" ? "status-accepted" : m.fee_status === "waived" ? "status-cancelled" : "status-pending"}`}>
                      {m.fee_status === "due" ? "Bekliyor" : m.fee_status === "paid" ? "Ödendi" : "Silindi"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn-secondary btn-sm"
                      onClick={() => navigate(`/matches/${m.id}`)}
                      data-testid="match-detail-link"
                    >
                      Detay →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
};

// ── Match Detail ──────────────────────────────────────────────────────────────
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

// ── Google Sheets Tab ─────────────────────────────────────────────────────────
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

// ── Reports Page ──────────────────────────────────────────────────────────────
const ReportsPage = () => {
  const [stats, setStats] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [tab, setTab] = React.useState("overview");
  const [marketTrends, setMarketTrends] = React.useState(null);
  const [perfScores, setPerfScores] = React.useState(null);
  const [revenue, setRevenue] = React.useState(null);
  const [reqStats, setReqStats] = React.useState(null);

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
    if (tab === "requests" && !reqStats) {
      axios.get("/stats/requests?period_days=30").then((r) => setReqStats(r.data)).catch(() => {});
    }
  }, [tab, marketTrends, perfScores, revenue, reqStats]);

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
  ];

  return (
    <Layout>
      <h1 className="page-title">📈 Raporlar &amp; Analitik</h1>
      <div className="tab-bar" style={{ marginBottom: "1.5rem" }}>
        {tabs.map((t) => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

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

      {tab === "requests" && (
        <div className="reports-grid">
          {reqStats ? (
            <>
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
              </div>
              <div className="report-card">
                <h3>📤 Gönderilen Talepler</h3>
                <div className="stats-list">
                  <div className="stats-row"><span className="stats-row-label">Toplam</span><span className="stats-row-value">{reqStats.outgoing?.total}</span></div>
                  {Object.entries(reqStats.outgoing?.by_status || {}).map(([s, c]) => (
                    <div key={s} className="stats-row"><span className="stats-row-label">{statusLabel(s)}</span><span className="stats-row-value">{c}</span></div>
                  ))}
                </div>
                <div style={{ marginTop: "1rem" }}>
                  <div style={{ fontSize: "0.85rem", color: "#6b7c93" }}>Kaçırma Oranı</div>
                  <div className="rate-indicator"><div className="rate-bar-outer"><div className="rate-bar-inner" style={{ width: `${reqStats.missed_rate}%`, background: "#ef4444" }} /></div><span style={{ fontWeight: 700, color: "#ef4444" }}>{reqStats.missed_rate}%</span></div>
                </div>
              </div>
            </>
          ) : <div className="page-center"><span className="loading-spin" /></div>}
        </div>
      )}

      {tab === "market" && (
        <div>
          <h2 style={{ marginBottom: "1rem" }}>🌍 Pazar Trendleri - Bölgesel Arz/Talep Dengesi</h2>
          {marketTrends ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
              {Object.entries(marketTrends).map(([key, data]) => (
                <div key={key} className="card" style={{ borderLeft: `4px solid ${data.balance === "dengeli" ? "#10b981" : data.balance === "talep_fazla" ? "#ef4444" : "#3b82f6"}` }}>
                  <h3>{data.label}</h3>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", margin: "1rem 0" }}>
                    <div style={{ textAlign: "center", padding: "0.5rem", background: "#f0fdf4", borderRadius: "0.5rem" }}><div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#10b981" }}>{data.supply}</div><div style={{ fontSize: "0.75rem", color: "#6b7c93" }}>Arz (Aktif İlan)</div></div>
                    <div style={{ textAlign: "center", padding: "0.5rem", background: "#fef2f2", borderRadius: "0.5rem" }}><div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#ef4444" }}>{data.demand}</div><div style={{ fontSize: "0.75rem", color: "#6b7c93" }}>Talep (30 gün)</div></div>
                  </div>
                  <div className="stats-list" style={{ fontSize: "0.85rem" }}>
                    <div className="stats-row"><span className="stats-row-label">Eşleşme</span><span className="stats-row-value">{data.matches}</span></div>
                    <div className="stats-row"><span className="stats-row-label">Ort. Fiyat</span><span className="stats-row-value">₺{data.avg_price?.toLocaleString("tr-TR")}</span></div>
                    <div className="stats-row"><span className="stats-row-label">Eşleşme Ücreti</span><span className="stats-row-value">₺{data.match_fee}</span></div>
                    <div className="stats-row"><span className="stats-row-label">Durum</span><span className="stats-row-value">{data.balance === "dengeli" ? "⚖️ Dengeli" : data.balance === "talep_fazla" ? "📈 Talep Fazla" : "📉 Arz Fazla"}</span></div>
                  </div>
                </div>
              ))}
            </div>
          ) : <div className="page-center"><span className="loading-spin" /></div>}
        </div>
      )}

      {tab === "performance" && (
        <div>
          {perfScores ? (
            <div className="reports-grid">
              <div className="report-card" style={{ gridColumn: "1 / -1" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "2rem" }}>
                  <div style={{ textAlign: "center", minWidth: "120px" }}>
                    <div style={{ fontSize: "3rem", fontWeight: 800, color: perfScores.grade === "A" ? "#10b981" : perfScores.grade === "B" ? "#3b82f6" : perfScores.grade === "C" ? "#f59e0b" : "#ef4444" }}>{perfScores.grade}</div>
                    <div style={{ fontSize: "1.2rem", fontWeight: 600 }}>{perfScores.score}/100</div>
                    <div style={{ color: "#6b7c93", fontSize: "0.8rem" }}>Son {perfScores.period_days} gün</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <h3>🏆 Performans Özeti</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem", marginTop: "1rem" }}>
                      <div><div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#10b981" }}>{perfScores.approval_rate}%</div><div style={{ color: "#6b7c93", fontSize: "0.8rem" }}>Onay Oranı</div></div>
                      <div><div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#ef4444" }}>{perfScores.cancellation_rate}%</div><div style={{ color: "#6b7c93", fontSize: "0.8rem" }}>İptal Oranı</div></div>
                      <div><div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#3b82f6" }}>{perfScores.avg_response_hours}h</div><div style={{ color: "#6b7c93", fontSize: "0.8rem" }}>Ort. Cevap Süresi</div></div>
                      <div><div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{perfScores.match_count}</div><div style={{ color: "#6b7c93", fontSize: "0.8rem" }}>Eşleşme</div></div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="report-card">
                <h3>📋 Talep Kırılımı</h3>
                <div className="stats-list">
                  <div className="stats-row"><span className="stats-row-label">Toplam Gelen</span><span className="stats-row-value">{perfScores.total_incoming_requests}</span></div>
                  <div className="stats-row"><span className="stats-row-label">Kabul</span><span className="stats-row-value text-green">{perfScores.accepted}</span></div>
                  <div className="stats-row"><span className="stats-row-label">Red</span><span className="stats-row-value text-red">{perfScores.rejected}</span></div>
                  <div className="stats-row"><span className="stats-row-label">Alternatif</span><span className="stats-row-value">{perfScores.alternative_offered}</span></div>
                  <div className="stats-row"><span className="stats-row-label">İptal</span><span className="stats-row-value">{perfScores.cancelled}</span></div>
                  <div className="stats-row"><span className="stats-row-label">Bekleyen</span><span className="stats-row-value">{perfScores.pending}</span></div>
                </div>
              </div>
            </div>
          ) : <div className="page-center"><span className="loading-spin" /></div>}
        </div>
      )}

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
    </Layout>
  );
};

// ── Admin Page ────────────────────────────────────────────────────────────────
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
    </Layout>
  );
};

// ── Inventory Management Page ─────────────────────────────────────────────────

const ROOM_TYPES_INV = [
  { value: "standart", label: "Standart Oda" },
  { value: "suite", label: "Suite" },
  { value: "bungalov", label: "Bungalov" },
  { value: "villa", label: "Villa" },
  { value: "apart", label: "Apart" },
  { value: "dag_evi", label: "Dağ Evi" },
  { value: "cadir", label: "Çadır/Glamping" },
  { value: "diger", label: "Diğer" },
];

const InventoryPage = () => {
  const [items, setItems] = React.useState([]);
  const [summary, setSummary] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [showCreate, setShowCreate] = React.useState(false);
  const [editItem, setEditItem] = React.useState(null);
  const [calendarItem, setCalendarItem] = React.useState(null);
  const [calendarData, setCalendarData] = React.useState(null);
  const [calendarMonth, setCalendarMonth] = React.useState(() => {
    const n = new Date();
    return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}`;
  });
  const [bulkModal, setBulkModal] = React.useState(null);
  const [deleteConfirm, setDeleteConfirm] = React.useState(null);

  const [form, setForm] = React.useState({
    room_type: "standart", room_type_name: "", total_rooms: 1,
    description: "", capacity_label: "", pax: 2,
  });
  const [bulkForm, setBulkForm] = React.useState({
    date_start: "", date_end: "", available_rooms: 0, price_per_night: "",
  });
  const [saving, setSaving] = React.useState(false);
  const [msg, setMsg] = React.useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [itemsRes, summaryRes] = await Promise.all([
        axios.get("/inventory"),
        axios.get("/inventory/summary/all"),
      ]);
      setItems(itemsRes.data);
      setSummary(summaryRes.data);
    } catch { }
    setLoading(false);
  };

  React.useEffect(() => { load(); }, []);

  const loadCalendar = async (invId, month) => {
    try {
      const res = await axios.get(`/inventory/${invId}/calendar`, { params: { month } });
      setCalendarData(res.data);
    } catch { }
  };

  React.useEffect(() => {
    if (calendarItem) loadCalendar(calendarItem._id || calendarItem.id, calendarMonth);
  }, [calendarItem, calendarMonth]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    try {
      await axios.post("/inventory", {
        room_type: form.room_type,
        room_type_name: form.room_type_name,
        total_rooms: parseInt(form.total_rooms),
        description: form.description || null,
        capacity_label: form.capacity_label || null,
        pax: parseInt(form.pax) || null,
      });
      setMsg("Envanter kalemi oluşturuldu!");
      setShowCreate(false);
      setForm({ room_type: "standart", room_type_name: "", total_rooms: 1, description: "", capacity_label: "", pax: 2 });
      load();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hata oluştu");
    }
    setSaving(false);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!editItem) return;
    setSaving(true);
    try {
      await axios.put(`/inventory/${editItem.id}`, {
        room_type_name: form.room_type_name || undefined,
        total_rooms: parseInt(form.total_rooms) || undefined,
        description: form.description || undefined,
        capacity_label: form.capacity_label || undefined,
        pax: parseInt(form.pax) || undefined,
      });
      setMsg("Güncellendi!");
      setEditItem(null);
      load();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hata");
    }
    setSaving(false);
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    try {
      await axios.delete(`/inventory/${deleteConfirm.id}`);
      setDeleteConfirm(null);
      load();
    } catch { }
  };

  const handleBulkAvailability = async (e) => {
    e.preventDefault();
    if (!bulkModal) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await axios.post("/inventory/availability/bulk", {
        inventory_id: bulkModal.id,
        date_start: bulkForm.date_start,
        date_end: bulkForm.date_end,
        available_rooms: parseInt(bulkForm.available_rooms),
        price_per_night: bulkForm.price_per_night ? parseFloat(bulkForm.price_per_night) : null,
      });
      setMsg(res.data.message);
      setBulkModal(null);
      setBulkForm({ date_start: "", date_end: "", available_rooms: 0, price_per_night: "" });
      load();
      if (calendarItem && calendarItem.id === bulkModal.id) {
        loadCalendar(calendarItem.id, calendarMonth);
      }
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hata");
    }
    setSaving(false);
  };

  const startEdit = (item) => {
    setEditItem(item);
    setForm({
      room_type: item.room_type,
      room_type_name: item.room_type_name,
      total_rooms: item.total_rooms,
      description: item.description || "",
      capacity_label: item.capacity_label || "",
      pax: item.pax || 2,
    });
  };

  const getDayColor = (day) => {
    if (!day.has_data) return "#f8fafc";
    const ratio = day.total_rooms > 0 ? day.booked_rooms / day.total_rooms : 0;
    if (ratio >= 1) return "#fee2e2";
    if (ratio >= 0.7) return "#fef3c7";
    if (ratio > 0) return "#dcfce7";
    return "#f0fdf4";
  };

  if (loading) return <Layout><div className="page-loading">Yükleniyor...</div></Layout>;

  return (
    <Layout>
      <div className="page-header">
        <h1>📦 Envanter Yönetimi</h1>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>+ Yeni Oda Tipi</button>
      </div>

      {msg && <div className="alert" style={{ marginBottom: "1rem" }}>{msg}</div>}

      {/* Özet Kartlar */}
      {summary && summary.items.length > 0 && (
        <div className="grid-3" style={{ marginBottom: "1.5rem" }}>
          {summary.items.map((s) => (
            <div key={s.inventory_id} className="card" style={{ padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <strong>{s.room_type_name}</strong>
                <span className="chip">{s.room_type}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.85rem" }}>
                <div>Toplam Oda: <strong>{s.total_rooms}</strong></div>
                <div>Bugün Müsait: <strong style={{ color: s.today_available > 0 ? "#166534" : "#991b1b" }}>{s.today_available}</strong></div>
                <div>Bugün Dolu: <strong>{s.today_booked}</strong></div>
                <div>Doluluk: <strong>{s.occupancy_rate}%</strong></div>
                {s.today_price && <div>Bugün Fiyat: <strong>{s.today_price}₺</strong></div>}
              </div>
              <div style={{ width: "100%", height: "6px", background: "#e2e8f0", borderRadius: "3px", marginTop: "0.5rem" }}>
                <div style={{
                  width: `${Math.min(s.occupancy_rate, 100)}%`,
                  height: "100%",
                  background: s.occupancy_rate > 80 ? "#ef4444" : s.occupancy_rate > 50 ? "#f59e0b" : "#22c55e",
                  borderRadius: "3px",
                  transition: "width 0.3s ease",
                }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Envanter Listesi */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <h3 style={{ marginBottom: "1rem" }}>Oda Tipleri ({items.length})</h3>
        {items.length === 0 ? (
          <div style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>
            Henüz envanter tanımı yok. Yeni oda tipi ekleyin.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Oda Tipi</th>
                  <th>Ad</th>
                  <th>Toplam</th>
                  <th>Kapasite</th>
                  <th>Kişi</th>
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td><span className="chip">{ROOM_TYPES_INV.find(r => r.value === item.room_type)?.label || item.room_type}</span></td>
                    <td><strong>{item.room_type_name}</strong></td>
                    <td>{item.total_rooms}</td>
                    <td>{item.capacity_label || "-"}</td>
                    <td>{item.pax || "-"}</td>
                    <td>
                      <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                        <button className="btn-secondary btn-sm" onClick={() => { setCalendarItem(item); }}>📅 Takvim</button>
                        <button className="btn-secondary btn-sm" onClick={() => setBulkModal(item)}>📋 Müsaitlik</button>
                        <button className="btn-secondary btn-sm" onClick={() => startEdit(item)}>✏️</button>
                        <button className="btn-danger btn-sm" onClick={() => setDeleteConfirm(item)}>🗑️</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Takvim Görünümü */}
      {calendarItem && calendarData && (
        <div className="card" style={{ padding: "1.25rem", marginTop: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h3>📅 {calendarData.room_type_name} - Takvim</h3>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <button className="btn-secondary btn-sm" onClick={() => {
                const [y, m] = calendarMonth.split("-").map(Number);
                const prev = m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
                setCalendarMonth(prev);
              }}>◀</button>
              <strong>{calendarMonth}</strong>
              <button className="btn-secondary btn-sm" onClick={() => {
                const [y, m] = calendarMonth.split("-").map(Number);
                const next = m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, "0")}`;
                setCalendarMonth(next);
              }}>▶</button>
              <button className="btn-ghost btn-sm" onClick={() => setCalendarItem(null)}>✕ Kapat</button>
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", fontSize: "0.75rem" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: "#f0fdf4", border: "1px solid #ccc" }} /> Boş
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: "#dcfce7", border: "1px solid #ccc" }} /> Müsait
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: "#fef3c7", border: "1px solid #ccc" }} /> Az Oda
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: "#fee2e2", border: "1px solid #ccc" }} /> Dolu
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "4px" }}>
            {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((d) => (
              <div key={d} style={{ textAlign: "center", fontWeight: 600, fontSize: "0.75rem", padding: "0.25rem", color: "#64748b" }}>{d}</div>
            ))}
            {calendarData.days.length > 0 && (() => {
              const firstDate = new Date(calendarData.days[0].date + "T00:00:00");
              const dayOfWeek = firstDate.getDay();
              const offset = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
              const blanks = Array(offset).fill(null);
              return [...blanks.map((_, i) => <div key={`b-${i}`} />), ...calendarData.days.map((day) => {
                const dayNum = new Date(day.date + "T00:00:00").getDate();
                return (
                  <div key={day.date} style={{
                    background: getDayColor(day),
                    border: "1px solid #e2e8f0",
                    borderRadius: "4px",
                    padding: "0.25rem",
                    textAlign: "center",
                    fontSize: "0.7rem",
                    minHeight: "52px",
                  }}>
                    <div style={{ fontWeight: 600, fontSize: "0.8rem" }}>{dayNum}</div>
                    {day.has_data ? (
                      <>
                        <div style={{ color: "#166534" }}>{day.available_rooms} müsait</div>
                        {day.price_per_night && <div style={{ color: "#7c3aed" }}>{day.price_per_night}₺</div>}
                      </>
                    ) : (
                      <div style={{ color: "#94a3b8" }}>-</div>
                    )}
                  </div>
                );
              })];
            })()}
          </div>
        </div>
      )}

      {/* Yeni Oda Tipi Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Yeni Oda Tipi Ekle">
        <form onSubmit={handleCreate}>
          <label className="field-label">Oda Tipi</label>
          <select className="field" value={form.room_type} onChange={(e) => setForm({ ...form, room_type: e.target.value })}>
            {ROOM_TYPES_INV.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <label className="field-label">Oda Adı</label>
          <input className="field" value={form.room_type_name} onChange={(e) => setForm({ ...form, room_type_name: e.target.value })} placeholder="Göl Manzaralı Bungalov" required />
          <label className="field-label">Toplam Oda Sayısı</label>
          <input className="field" type="number" min={1} value={form.total_rooms} onChange={(e) => setForm({ ...form, total_rooms: e.target.value })} required />
          <label className="field-label">Kapasite Etiketi (2+1, 3+1 vb.)</label>
          <input className="field" value={form.capacity_label} onChange={(e) => setForm({ ...form, capacity_label: e.target.value })} placeholder="2+1" />
          <label className="field-label">Kişi Sayısı</label>
          <input className="field" type="number" min={1} value={form.pax} onChange={(e) => setForm({ ...form, pax: e.target.value })} />
          <label className="field-label">Açıklama</label>
          <textarea className="field" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>İptal</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Kaydediliyor..." : "Kaydet"}</button>
          </div>
        </form>
      </Modal>

      {/* Düzenle Modal */}
      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Oda Tipini Düzenle">
        <form onSubmit={handleUpdate}>
          <label className="field-label">Oda Adı</label>
          <input className="field" value={form.room_type_name} onChange={(e) => setForm({ ...form, room_type_name: e.target.value })} required />
          <label className="field-label">Toplam Oda Sayısı</label>
          <input className="field" type="number" min={1} value={form.total_rooms} onChange={(e) => setForm({ ...form, total_rooms: e.target.value })} required />
          <label className="field-label">Kapasite Etiketi</label>
          <input className="field" value={form.capacity_label} onChange={(e) => setForm({ ...form, capacity_label: e.target.value })} />
          <label className="field-label">Kişi Sayısı</label>
          <input className="field" type="number" min={1} value={form.pax} onChange={(e) => setForm({ ...form, pax: e.target.value })} />
          <label className="field-label">Açıklama</label>
          <textarea className="field" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => setEditItem(null)}>İptal</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Kaydediliyor..." : "Güncelle"}</button>
          </div>
        </form>
      </Modal>

      {/* Toplu Müsaitlik Modal */}
      <Modal open={!!bulkModal} onClose={() => setBulkModal(null)} title={`Müsaitlik Ayarla — ${bulkModal?.room_type_name || ""}`}>
        <form onSubmit={handleBulkAvailability}>
          <label className="field-label">Başlangıç Tarihi</label>
          <input className="field" type="date" value={bulkForm.date_start} onChange={(e) => setBulkForm({ ...bulkForm, date_start: e.target.value })} required />
          <label className="field-label">Bitiş Tarihi</label>
          <input className="field" type="date" value={bulkForm.date_end} onChange={(e) => setBulkForm({ ...bulkForm, date_end: e.target.value })} required />
          <label className="field-label">Müsait Oda Sayısı (max: {bulkModal?.total_rooms})</label>
          <input className="field" type="number" min={0} max={bulkModal?.total_rooms || 99} value={bulkForm.available_rooms}
            onChange={(e) => setBulkForm({ ...bulkForm, available_rooms: e.target.value })} required />
          <label className="field-label">Gecelik Fiyat (₺, opsiyonel)</label>
          <input className="field" type="number" min={0} step="0.01" value={bulkForm.price_per_night}
            onChange={(e) => setBulkForm({ ...bulkForm, price_per_night: e.target.value })} placeholder="Boş bırakılabilir" />
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => setBulkModal(null)}>İptal</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Kaydediliyor..." : "Uygula"}</button>
          </div>
        </form>
      </Modal>

      {/* Silme Onay */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Oda Tipini Sil"
        message={`"${deleteConfirm?.room_type_name}" oda tipini ve tüm müsaitlik verilerini silmek istediğinize emin misiniz?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Layout>
  );
};

// ── Pricing Engine Page ──────────────────────────────────────────────────────

const RULE_TYPES = [
  { value: "seasonal", label: "Sezon", icon: "🌞" },
  { value: "weekend", label: "Hafta Sonu", icon: "📅" },
  { value: "occupancy", label: "Doluluk", icon: "📊" },
  { value: "early_bird", label: "Erken Rezervasyon", icon: "🐦" },
  { value: "last_minute", label: "Son Dakika", icon: "⏰" },
  { value: "holiday", label: "Tatil/Bayram", icon: "🎉" },
];

const PricingPage = () => {
  const [rules, setRules] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [showCreate, setShowCreate] = React.useState(false);
  const [editRule, setEditRule] = React.useState(null);
  const [deleteConfirm, setDeleteConfirm] = React.useState(null);
  const [msg, setMsg] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [tab, setTab] = React.useState("rules");

  // Calculator state
  const [calcForm, setCalcForm] = React.useState({
    room_type: "standart", date_start: "", date_end: "", base_price: "",
  });
  const [calcResult, setCalcResult] = React.useState(null);
  const [calcLoading, setCalcLoading] = React.useState(false);

  // Market comparison state
  const [marketData, setMarketData] = React.useState(null);
  const [marketRoom, setMarketRoom] = React.useState("");
  const [marketRegion, setMarketRegion] = React.useState("");
  const [marketLoading, setMarketLoading] = React.useState(false);

  // Price history
  const [historyData, setHistoryData] = React.useState(null);
  const [historyLoading, setHistoryLoading] = React.useState(false);

  const defaultRule = {
    name: "", rule_type: "seasonal", room_type: "", multiplier: 1.0,
    date_start: "", date_end: "", occupancy_threshold_min: "", occupancy_threshold_max: "",
    days_before_min: "", days_before_max: "", weekend_days: [5, 6],
    is_active: true, priority: 0,
  };
  const [ruleForm, setRuleForm] = React.useState(defaultRule);

  const loadRules = async () => {
    try {
      const res = await axios.get("/pricing/rules");
      setRules(res.data);
    } catch { }
    setLoading(false);
  };

  React.useEffect(() => { loadRules(); }, []);

  const handleCreateRule = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    try {
      const payload = {
        name: ruleForm.name,
        rule_type: ruleForm.rule_type,
        multiplier: parseFloat(ruleForm.multiplier),
        room_type: ruleForm.room_type || null,
        is_active: ruleForm.is_active,
        priority: parseInt(ruleForm.priority) || 0,
      };
      if (ruleForm.rule_type === "seasonal" || ruleForm.rule_type === "holiday") {
        payload.date_start = ruleForm.date_start || null;
        payload.date_end = ruleForm.date_end || null;
      }
      if (ruleForm.rule_type === "occupancy") {
        payload.occupancy_threshold_min = ruleForm.occupancy_threshold_min ? parseFloat(ruleForm.occupancy_threshold_min) : null;
        payload.occupancy_threshold_max = ruleForm.occupancy_threshold_max ? parseFloat(ruleForm.occupancy_threshold_max) : null;
      }
      if (ruleForm.rule_type === "early_bird" || ruleForm.rule_type === "last_minute") {
        payload.days_before_min = ruleForm.days_before_min ? parseInt(ruleForm.days_before_min) : null;
        payload.days_before_max = ruleForm.days_before_max ? parseInt(ruleForm.days_before_max) : null;
      }
      if (ruleForm.rule_type === "weekend") {
        payload.weekend_days = ruleForm.weekend_days;
      }

      if (editRule) {
        await axios.put(`/pricing/rules/${editRule.id}`, payload);
        setMsg("Kural güncellendi!");
      } else {
        await axios.post("/pricing/rules", payload);
        setMsg("Kural oluşturuldu!");
      }
      setShowCreate(false);
      setEditRule(null);
      setRuleForm(defaultRule);
      loadRules();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hata oluştu");
    }
    setSaving(false);
  };

  const handleDeleteRule = async () => {
    if (!deleteConfirm) return;
    try {
      await axios.delete(`/pricing/rules/${deleteConfirm.id}`);
      setDeleteConfirm(null);
      loadRules();
    } catch { }
  };

  const handleCalculate = async (e) => {
    e.preventDefault();
    setCalcLoading(true);
    setCalcResult(null);
    try {
      const res = await axios.post("/pricing/calculate", {
        room_type: calcForm.room_type,
        date_start: calcForm.date_start,
        date_end: calcForm.date_end,
        base_price: parseFloat(calcForm.base_price),
      });
      setCalcResult(res.data);
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hesaplama hatası");
    }
    setCalcLoading(false);
  };

  const loadMarket = async () => {
    setMarketLoading(true);
    try {
      const params = {};
      if (marketRoom) params.room_type = marketRoom;
      if (marketRegion) params.region = marketRegion;
      const res = await axios.get("/pricing/market-comparison", { params });
      setMarketData(res.data);
    } catch { }
    setMarketLoading(false);
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await axios.get("/pricing/history", { params: { months: 6 } });
      setHistoryData(res.data);
    } catch { }
    setHistoryLoading(false);
  };

  const startEditRule = (rule) => {
    setEditRule(rule);
    setRuleForm({
      name: rule.name,
      rule_type: rule.rule_type,
      room_type: rule.room_type || "",
      multiplier: rule.multiplier,
      date_start: rule.date_start || "",
      date_end: rule.date_end || "",
      occupancy_threshold_min: rule.occupancy_threshold_min ?? "",
      occupancy_threshold_max: rule.occupancy_threshold_max ?? "",
      days_before_min: rule.days_before_min ?? "",
      days_before_max: rule.days_before_max ?? "",
      weekend_days: rule.weekend_days || [5, 6],
      is_active: rule.is_active,
      priority: rule.priority,
    });
    setShowCreate(true);
  };

  const multiplierLabel = (m) => {
    if (m > 1) return `+${Math.round((m - 1) * 100)}%`;
    if (m < 1) return `-${Math.round((1 - m) * 100)}%`;
    return "Değişiklik yok";
  };

  return (
    <Layout>
      <div className="page-header">
        <h1>💰 Fiyatlama Motoru</h1>
      </div>

      {msg && <div className="alert" style={{ marginBottom: "1rem" }}>{msg}</div>}

      {/* Tabs */}
      <div className="tab-bar" style={{ marginBottom: "1rem" }}>
        <button className={`tab-btn ${tab === "rules" ? "active" : ""}`} onClick={() => setTab("rules")}>📋 Kurallar</button>
        <button className={`tab-btn ${tab === "calculator" ? "active" : ""}`} onClick={() => setTab("calculator")}>🧮 Hesaplayıcı</button>
        <button className={`tab-btn ${tab === "market" ? "active" : ""}`} onClick={() => { setTab("market"); if (!marketData) loadMarket(); }}>📊 Piyasa</button>
        <button className={`tab-btn ${tab === "history" ? "active" : ""}`} onClick={() => { setTab("history"); if (!historyData) loadHistory(); }}>📈 Geçmiş</button>
      </div>

      {/* Kurallar Tab */}
      {tab === "rules" && (
        <div className="card" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h3>Fiyatlama Kuralları ({rules.length})</h3>
            <button className="btn-primary btn-sm" onClick={() => { setEditRule(null); setRuleForm(defaultRule); setShowCreate(true); }}>+ Yeni Kural</button>
          </div>

          {rules.length === 0 ? (
            <div style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>
              Henüz fiyatlama kuralı yok. Sezon, hafta sonu veya doluluk bazlı kurallar ekleyebilirsiniz.
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Kural Adı</th>
                    <th>Tip</th>
                    <th>Çarpan</th>
                    <th>Oda Tipi</th>
                    <th>Durum</th>
                    <th>Öncelik</th>
                    <th>İşlem</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => {
                    const rt = RULE_TYPES.find(r => r.value === rule.rule_type);
                    return (
                      <tr key={rule.id}>
                        <td><strong>{rule.name}</strong></td>
                        <td>{rt ? `${rt.icon} ${rt.label}` : rule.rule_type}</td>
                        <td>
                          <span style={{
                            color: rule.multiplier > 1 ? "#dc2626" : rule.multiplier < 1 ? "#16a34a" : "#64748b",
                            fontWeight: 600,
                          }}>
                            x{rule.multiplier} ({multiplierLabel(rule.multiplier)})
                          </span>
                        </td>
                        <td>{rule.room_type || "Tümü"}</td>
                        <td>
                          <span className={`chip ${rule.is_active ? "chip-green" : "chip-gray"}`}>
                            {rule.is_active ? "Aktif" : "Pasif"}
                          </span>
                        </td>
                        <td>{rule.priority}</td>
                        <td>
                          <div style={{ display: "flex", gap: "0.3rem" }}>
                            <button className="btn-secondary btn-sm" onClick={() => startEditRule(rule)}>✏️</button>
                            <button className="btn-danger btn-sm" onClick={() => setDeleteConfirm(rule)}>🗑️</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Hesaplayıcı Tab */}
      {tab === "calculator" && (
        <div className="card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "1rem" }}>🧮 Dinamik Fiyat Hesaplayıcı</h3>
          <form onSubmit={handleCalculate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <div>
              <label className="field-label">Oda Tipi</label>
              <select className="field" value={calcForm.room_type} onChange={(e) => setCalcForm({ ...calcForm, room_type: e.target.value })}>
                {ROOM_TYPES_INV.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label">Baz Fiyat (₺/gece)</label>
              <input className="field" type="number" min={0} step="0.01" value={calcForm.base_price}
                onChange={(e) => setCalcForm({ ...calcForm, base_price: e.target.value })} required />
            </div>
            <div>
              <label className="field-label">Başlangıç</label>
              <input className="field" type="date" value={calcForm.date_start}
                onChange={(e) => setCalcForm({ ...calcForm, date_start: e.target.value })} required />
            </div>
            <div>
              <label className="field-label">Bitiş</label>
              <input className="field" type="date" value={calcForm.date_end}
                onChange={(e) => setCalcForm({ ...calcForm, date_end: e.target.value })} required />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <button type="submit" className="btn-primary" disabled={calcLoading}>{calcLoading ? "Hesaplanıyor..." : "Hesapla"}</button>
            </div>
          </form>

          {calcResult && (
            <div style={{ marginTop: "1.25rem" }}>
              <div className="grid-3" style={{ marginBottom: "1rem" }}>
                <div className="card" style={{ padding: "1rem", textAlign: "center", background: "#f0fdf4" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Toplam Fiyat</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#166534" }}>{calcResult.total_price}₺</div>
                </div>
                <div className="card" style={{ padding: "1rem", textAlign: "center", background: "#eff6ff" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Ort. Gece</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#1e40af" }}>{calcResult.average_price}₺</div>
                </div>
                <div className="card" style={{ padding: "1rem", textAlign: "center", background: "#faf5ff" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Gece Sayısı</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#7c3aed" }}>{calcResult.night_count}</div>
                </div>
              </div>

              <h4 style={{ marginBottom: "0.5rem" }}>Günlük Dağılım</h4>
              <div className="table-wrap" style={{ maxHeight: "300px", overflowY: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Tarih</th>
                      <th>Baz Fiyat</th>
                      <th>Son Fiyat</th>
                      <th>Çarpan</th>
                      <th>Uygulanan Kurallar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calcResult.daily_breakdown.map((d) => (
                      <tr key={d.date}>
                        <td>{d.date}</td>
                        <td>{d.base_price}₺</td>
                        <td style={{ fontWeight: 600, color: d.final_price > d.base_price ? "#dc2626" : d.final_price < d.base_price ? "#16a34a" : "#1e293b" }}>
                          {d.final_price}₺
                        </td>
                        <td>x{d.final_multiplier}</td>
                        <td>
                          {d.applied_rules.length === 0 ? <span style={{ color: "#94a3b8" }}>-</span> :
                            d.applied_rules.map(r => <span key={r.rule_id} className="chip" style={{ marginRight: "0.25rem" }}>{r.name}</span>)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Piyasa Tab */}
      {tab === "market" && (
        <div className="card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "1rem" }}>📊 Piyasa Karşılaştırması</h3>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            <select className="field" style={{ width: "auto" }} value={marketRoom} onChange={(e) => setMarketRoom(e.target.value)}>
              <option value="">Tüm Oda Tipleri</option>
              {ROOM_TYPES_INV.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
            <select className="field" style={{ width: "auto" }} value={marketRegion} onChange={(e) => setMarketRegion(e.target.value)}>
              <option value="">Tüm Bölgeler</option>
              <option value="Sapanca">Sapanca</option>
              <option value="Kartepe">Kartepe</option>
              <option value="Abant">Abant</option>
              <option value="Ayder">Ayder</option>
              <option value="Kas">Kaş</option>
              <option value="Alacati">Alaçatı</option>
              <option value="Maşukiye">Maşukiye</option>
            </select>
            <button className="btn-primary btn-sm" onClick={loadMarket} disabled={marketLoading}>
              {marketLoading ? "Yükleniyor..." : "Karşılaştır"}
            </button>
          </div>

          {marketData && (
            <div>
              <div className="grid-3" style={{ marginBottom: "1rem" }}>
                <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Piyasa Ort. (min)</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700 }}>{marketData.avg_price_min ? `${marketData.avg_price_min}₺` : "-"}</div>
                </div>
                <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Sizin Ort.</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#7c3aed" }}>{marketData.my_avg_price ? `${marketData.my_avg_price}₺` : "-"}</div>
                </div>
                <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>İlan Sayısı</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700 }}>{marketData.sample_size}</div>
                </div>
              </div>

              {marketData.min_price && marketData.max_price && (
                <div style={{ background: "#f8fafc", padding: "1rem", borderRadius: "0.5rem", marginBottom: "1rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                    <span>Min: {marketData.min_price}₺</span>
                    <span>Medyan: {marketData.median_price}₺</span>
                    <span>Max: {marketData.max_price}₺</span>
                  </div>
                  <div style={{ width: "100%", height: "8px", background: "#e2e8f0", borderRadius: "4px", position: "relative" }}>
                    {marketData.my_avg_price && (
                      <div style={{
                        position: "absolute",
                        left: `${Math.min(((marketData.my_avg_price - marketData.min_price) / (marketData.max_price - marketData.min_price)) * 100, 100)}%`,
                        top: "-4px",
                        width: "16px", height: "16px",
                        background: "#7c3aed", borderRadius: "50%", border: "2px solid #fff",
                        transform: "translateX(-50%)",
                      }} title={`Sizin fiyatınız: ${marketData.my_avg_price}₺`} />
                    )}
                  </div>
                </div>
              )}

              <div className="alert" style={{
                background: marketData.recommendation.includes("indirim") ? "#fef3c7" :
                  marketData.recommendation.includes("artış") ? "#dcfce7" : "#eff6ff",
                borderLeft: "4px solid",
                borderLeftColor: marketData.recommendation.includes("indirim") ? "#f59e0b" :
                  marketData.recommendation.includes("artış") ? "#22c55e" : "#3b82f6",
              }}>
                💡 <strong>Öneri:</strong> {marketData.recommendation}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Geçmiş Tab */}
      {tab === "history" && (
        <div className="card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "1rem" }}>📈 Fiyat Geçmişi (Son 6 Ay)</h3>
          {historyLoading ? <div>Yükleniyor...</div> : historyData && historyData.history.length > 0 ? (
            <div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Ay</th>
                      <th>Ort. Min Fiyat</th>
                      <th>Ort. Max Fiyat</th>
                      <th>İlan Sayısı</th>
                      <th>En Düşük</th>
                      <th>En Yüksek</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyData.history.map((h) => (
                      <tr key={h.month}>
                        <td><strong>{h.month}</strong></td>
                        <td>{h.avg_price_min}₺</td>
                        <td>{h.avg_price_max}₺</td>
                        <td>{h.listing_count}</td>
                        <td style={{ color: "#16a34a" }}>{h.min_price}₺</td>
                        <td style={{ color: "#dc2626" }}>{h.max_price}₺</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Simple bar chart */}
              <div style={{ marginTop: "1.25rem" }}>
                <h4 style={{ marginBottom: "0.5rem" }}>Fiyat Trendi</h4>
                <div style={{ display: "flex", alignItems: "flex-end", gap: "0.5rem", height: "150px" }}>
                  {historyData.history.map((h) => {
                    const maxPrice = Math.max(...historyData.history.map(x => x.avg_price_max));
                    const pct = maxPrice > 0 ? Math.max((h.avg_price_max / maxPrice) * 100, 5) : 5;
                    return (
                      <div key={h.month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <div style={{ fontSize: "0.7rem", marginBottom: "0.25rem" }}>{h.avg_price_max}₺</div>
                        <div style={{
                          width: "100%", height: `${pct}%`,
                          background: "linear-gradient(to top, #7c3aed, #a78bfa)",
                          borderRadius: "4px 4px 0 0",
                          minHeight: "4px",
                        }} />
                        <div style={{ fontSize: "0.65rem", marginTop: "0.25rem", color: "#64748b" }}>{h.month.split("-")[1]}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>Henüz fiyat geçmişi yok.</div>
          )}
        </div>
      )}

      {/* Kural Oluştur/Düzenle Modal */}
      <Modal open={showCreate} onClose={() => { setShowCreate(false); setEditRule(null); }} title={editRule ? "Kuralı Düzenle" : "Yeni Fiyatlama Kuralı"} size="lg">
        <form onSubmit={handleCreateRule}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <div>
              <label className="field-label">Kural Adı</label>
              <input className="field" value={ruleForm.name} onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })} placeholder="Yaz Sezonu %30" required />
            </div>
            <div>
              <label className="field-label">Kural Tipi</label>
              <select className="field" value={ruleForm.rule_type} onChange={(e) => setRuleForm({ ...ruleForm, rule_type: e.target.value })}>
                {RULE_TYPES.map(r => <option key={r.value} value={r.value}>{r.icon} {r.label}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label">Fiyat Çarpanı (1.0 = değişiklik yok)</label>
              <input className="field" type="number" step="0.01" min="0.1" max="5" value={ruleForm.multiplier}
                onChange={(e) => setRuleForm({ ...ruleForm, multiplier: e.target.value })} required />
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.25rem" }}>
                {ruleForm.multiplier > 1 ? `${Math.round((ruleForm.multiplier - 1) * 100)}% artış` :
                  ruleForm.multiplier < 1 ? `${Math.round((1 - ruleForm.multiplier) * 100)}% indirim` : "Değişiklik yok"}
              </div>
            </div>
            <div>
              <label className="field-label">Oda Tipi (boş = tümü)</label>
              <select className="field" value={ruleForm.room_type} onChange={(e) => setRuleForm({ ...ruleForm, room_type: e.target.value })}>
                <option value="">Tüm Oda Tipleri</option>
                {ROOM_TYPES_INV.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>

            {/* Conditional fields based on rule_type */}
            {(ruleForm.rule_type === "seasonal" || ruleForm.rule_type === "holiday") && (
              <>
                <div>
                  <label className="field-label">Başlangıç Tarihi</label>
                  <input className="field" type="date" value={ruleForm.date_start} onChange={(e) => setRuleForm({ ...ruleForm, date_start: e.target.value })} />
                </div>
                <div>
                  <label className="field-label">Bitiş Tarihi</label>
                  <input className="field" type="date" value={ruleForm.date_end} onChange={(e) => setRuleForm({ ...ruleForm, date_end: e.target.value })} />
                </div>
              </>
            )}

            {ruleForm.rule_type === "occupancy" && (
              <>
                <div>
                  <label className="field-label">Min Doluluk Oranı (0-1)</label>
                  <input className="field" type="number" step="0.1" min="0" max="1" value={ruleForm.occupancy_threshold_min}
                    onChange={(e) => setRuleForm({ ...ruleForm, occupancy_threshold_min: e.target.value })} placeholder="0.7" />
                </div>
                <div>
                  <label className="field-label">Max Doluluk Oranı (0-1)</label>
                  <input className="field" type="number" step="0.1" min="0" max="1" value={ruleForm.occupancy_threshold_max}
                    onChange={(e) => setRuleForm({ ...ruleForm, occupancy_threshold_max: e.target.value })} placeholder="1.0" />
                </div>
              </>
            )}

            {(ruleForm.rule_type === "early_bird" || ruleForm.rule_type === "last_minute") && (
              <>
                <div>
                  <label className="field-label">Min Gün Öncesi</label>
                  <input className="field" type="number" min="0" value={ruleForm.days_before_min}
                    onChange={(e) => setRuleForm({ ...ruleForm, days_before_min: e.target.value })} placeholder={ruleForm.rule_type === "early_bird" ? "30" : "0"} />
                </div>
                <div>
                  <label className="field-label">Max Gün Öncesi</label>
                  <input className="field" type="number" min="0" value={ruleForm.days_before_max}
                    onChange={(e) => setRuleForm({ ...ruleForm, days_before_max: e.target.value })} placeholder={ruleForm.rule_type === "early_bird" ? "365" : "7"} />
                </div>
              </>
            )}

            {ruleForm.rule_type === "weekend" && (
              <div style={{ gridColumn: "1 / -1" }}>
                <label className="field-label">Hafta Sonu Günleri</label>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((day, idx) => (
                    <label key={idx} style={{ display: "flex", alignItems: "center", gap: "0.25rem", cursor: "pointer" }}>
                      <input type="checkbox" checked={ruleForm.weekend_days.includes(idx)}
                        onChange={() => {
                          const days = ruleForm.weekend_days.includes(idx)
                            ? ruleForm.weekend_days.filter(d => d !== idx)
                            : [...ruleForm.weekend_days, idx];
                          setRuleForm({ ...ruleForm, weekend_days: days });
                        }} />
                      {day}
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div>
              <label className="field-label">Öncelik (yüksek = önce uygulanır)</label>
              <input className="field" type="number" value={ruleForm.priority}
                onChange={(e) => setRuleForm({ ...ruleForm, priority: e.target.value })} />
            </div>
            <div style={{ display: "flex", alignItems: "end" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                <input type="checkbox" checked={ruleForm.is_active}
                  onChange={(e) => setRuleForm({ ...ruleForm, is_active: e.target.checked })} />
                Aktif
              </label>
            </div>
          </div>

          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => { setShowCreate(false); setEditRule(null); }}>İptal</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Kaydediliyor..." : editRule ? "Güncelle" : "Oluştur"}</button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!deleteConfirm}
        title="Kuralı Sil"
        message={`"${deleteConfirm?.name}" fiyatlama kuralını silmek istediğinize emin misiniz?`}
        onConfirm={handleDeleteRule}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Layout>
  );
};

// ── Performance Dashboard Page ────────────────────────────────────────────────

const PerformancePage = () => {
  const { hotel } = useAuth();
  const [health, setHealth] = React.useState(null);
  const [benchmark, setBenchmark] = React.useState(null);
  const [indexes, setIndexes] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [benchLoading, setBenchLoading] = React.useState(false);
  const [tab, setTab] = React.useState("health");

  const loadHealth = async () => {
    try {
      const res = await axios.get("/performance/health");
      setHealth(res.data);
    } catch { }
    setLoading(false);
  };

  const runBenchmark = async () => {
    setBenchLoading(true);
    try {
      const res = await axios.get("/performance/benchmark");
      setBenchmark(res.data);
    } catch { }
    setBenchLoading(false);
  };

  const loadIndexes = async () => {
    try {
      const res = await axios.get("/performance/db-indexes");
      setIndexes(res.data);
    } catch { }
  };

  React.useEffect(() => { loadHealth(); }, []);

  if (!hotel?.is_admin) {
    return <Layout><div className="alert" style={{ background: "#fee2e2" }}>Bu sayfa sadece admin kullanıcılar içindir.</div></Layout>;
  }

  return (
    <Layout>
      <div className="page-header">
        <h1>🚀 Performans Merkezi</h1>
      </div>

      <div className="tab-bar" style={{ marginBottom: "1rem" }}>
        <button className={`tab-btn ${tab === "health" ? "active" : ""}`} onClick={() => setTab("health")}>💚 Sağlık</button>
        <button className={`tab-btn ${tab === "benchmark" ? "active" : ""}`} onClick={() => { setTab("benchmark"); if (!benchmark) runBenchmark(); }}>⚡ Benchmark</button>
        <button className={`tab-btn ${tab === "indexes" ? "active" : ""}`} onClick={() => { setTab("indexes"); if (!indexes) loadIndexes(); }}>🗂️ İndeksler</button>
      </div>

      {/* Sağlık Tab */}
      {tab === "health" && (
        <div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
            <button className="btn-primary btn-sm" onClick={loadHealth} disabled={loading}>🔄 Yenile</button>
          </div>

          {health && (
            <div>
              <div className="grid-3" style={{ marginBottom: "1rem" }}>
                <div className="card" style={{
                  padding: "1.25rem", textAlign: "center",
                  background: health.status === "healthy" ? "#f0fdf4" : "#fef3c7",
                  borderLeft: `4px solid ${health.status === "healthy" ? "#22c55e" : "#f59e0b"}`,
                }}>
                  <div style={{ fontSize: "2rem" }}>{health.status === "healthy" ? "✅" : "⚠️"}</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>{health.status === "healthy" ? "Sağlıklı" : "Dikkat"}</div>
                </div>
                <div className="card" style={{ padding: "1.25rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Toplam Yanıt</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{health.total_response_ms}ms</div>
                </div>
                <div className="card" style={{ padding: "1.25rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>MongoDB</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: health.checks?.mongodb?.status === "ok" ? "#16a34a" : "#dc2626" }}>
                    {health.checks?.mongodb?.latency_ms || "-"}ms
                  </div>
                </div>
              </div>

              {health.checks?.collections && (
                <div className="card" style={{ padding: "1.25rem" }}>
                  <h3 style={{ marginBottom: "0.75rem" }}>Koleksiyon Sayıları</h3>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>Koleksiyon</th><th>Kayıt Sayısı</th></tr></thead>
                      <tbody>
                        {Object.entries(health.checks.collections.counts).map(([name, count]) => (
                          <tr key={name}><td><strong>{name}</strong></td><td>{count}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "0.5rem" }}>
                    Sorgu süresi: {health.checks.collections.query_time_ms}ms
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Benchmark Tab */}
      {tab === "benchmark" && (
        <div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
            <button className="btn-primary btn-sm" onClick={runBenchmark} disabled={benchLoading}>
              {benchLoading ? "Test çalışıyor..." : "⚡ Benchmark Çalıştır"}
            </button>
          </div>

          {benchmark && (
            <div>
              <div className="grid-3" style={{ marginBottom: "1rem" }}>
                <div className="card" style={{
                  padding: "1.25rem", textAlign: "center",
                  background: benchmark.grade === "A" ? "#f0fdf4" : benchmark.grade === "B" ? "#eff6ff" : "#fef3c7",
                }}>
                  <div style={{ fontSize: "2.5rem", fontWeight: 700, color: benchmark.grade === "A" ? "#16a34a" : benchmark.grade === "B" ? "#2563eb" : "#f59e0b" }}>
                    {benchmark.grade}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "#64748b" }}>{benchmark.grade_description}</div>
                </div>
                <div className="card" style={{ padding: "1.25rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Toplam Süre</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{benchmark.total_ms}ms</div>
                </div>
                <div className="card" style={{ padding: "1.25rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Test Sayısı</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{Object.keys(benchmark.benchmarks).length}</div>
                </div>
              </div>

              <div className="card" style={{ padding: "1.25rem" }}>
                <h3 style={{ marginBottom: "0.75rem" }}>Test Detayları</h3>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Test</th><th>Süre (ms)</th><th>Durum</th></tr></thead>
                    <tbody>
                      {Object.entries(benchmark.benchmarks).map(([name, data]) => (
                        <tr key={name}>
                          <td><strong>{name.replace(/_/g, " ")}</strong></td>
                          <td>{data.time_ms}ms</td>
                          <td>
                            <span style={{
                              padding: "0.15rem 0.5rem", borderRadius: "999px", fontSize: "0.75rem",
                              background: data.time_ms < 10 ? "#dcfce7" : data.time_ms < 50 ? "#eff6ff" : "#fef3c7",
                              color: data.time_ms < 10 ? "#166534" : data.time_ms < 50 ? "#1e40af" : "#92400e",
                            }}>
                              {data.time_ms < 10 ? "Hızlı" : data.time_ms < 50 ? "Normal" : "Yavaş"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Visual Bar Chart */}
              <div className="card" style={{ padding: "1.25rem", marginTop: "1rem" }}>
                <h3 style={{ marginBottom: "0.75rem" }}>Performans Grafiği</h3>
                {Object.entries(benchmark.benchmarks).map(([name, data]) => {
                  const maxMs = Math.max(...Object.values(benchmark.benchmarks).map(d => d.time_ms));
                  const pct = maxMs > 0 ? Math.max((data.time_ms / maxMs) * 100, 2) : 2;
                  return (
                    <div key={name} style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
                      <div style={{ width: "140px", fontSize: "0.75rem", textAlign: "right", color: "#64748b" }}>{name.replace(/_/g, " ")}</div>
                      <div style={{ flex: 1, height: "20px", background: "#f1f5f9", borderRadius: "4px", overflow: "hidden" }}>
                        <div style={{
                          width: `${pct}%`, height: "100%",
                          background: data.time_ms < 10 ? "#22c55e" : data.time_ms < 50 ? "#3b82f6" : "#f59e0b",
                          borderRadius: "4px",
                          transition: "width 0.5s ease",
                        }} />
                      </div>
                      <div style={{ width: "60px", fontSize: "0.75rem", fontWeight: 600 }}>{data.time_ms}ms</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* İndeksler Tab */}
      {tab === "indexes" && (
        <div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
            <button className="btn-primary btn-sm" onClick={loadIndexes}>🔄 Yenile</button>
          </div>

          {indexes && (
            <div className="card" style={{ padding: "1.25rem" }}>
              <h3 style={{ marginBottom: "0.75rem" }}>MongoDB İndeksleri</h3>
              {Object.entries(indexes).map(([coll, idxs]) => (
                <div key={coll} style={{ marginBottom: "1rem" }}>
                  <h4 style={{ fontSize: "0.9rem", color: "#1e40af", marginBottom: "0.25rem" }}>📁 {coll}</h4>
                  {idxs.error ? (
                    <div style={{ color: "#dc2626", fontSize: "0.8rem" }}>Hata: {idxs.error}</div>
                  ) : (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
                      {Object.entries(idxs).map(([idxName, info]) => (
                        <span key={idxName} className="chip" style={{ fontSize: "0.7rem" }}>
                          {idxName}: {info.keys?.map(k => k.join(":")).join(", ")}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Layout>
  );
};

// =============================================================================
// ── Payments Page ─────────────────────────────────────────────────────────────
// =============================================================================
const PaymentsPage = () => {
  const [payments, setPayments] = React.useState([]);
  const [matches, setMatches] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [payModal, setPayModal] = React.useState(null);
  const [processing, setProcessing] = React.useState(false);
  const [msg, setMsg] = React.useState("");

  const load = async () => {
    try {
      const [pRes, mRes] = await Promise.all([
        axios.get("/payments"),
        axios.get("/matches"),
      ]);
      setPayments(pRes.data);
      setMatches(mRes.data);
    } catch {} finally { setLoading(false); }
  };

  React.useEffect(() => { load(); }, []);

  const unpaidMatches = matches.filter((m) => m.fee_status !== "paid" && !payments.some((p) => p.match_id === m.id && p.status === "completed"));

  const initiatePayment = async (matchId) => {
    setProcessing(true); setMsg("");
    try {
      const res = await axios.post("/payments/initiate", { match_id: matchId, method: "credit_card" });
      setPayModal(res.data);
    } catch (e) { setMsg(e.response?.data?.detail || "Hata oluştu"); }
    finally { setProcessing(false); }
  };

  const completePayment = async (paymentId) => {
    setProcessing(true); setMsg("");
    try {
      await axios.post(`/payments/${paymentId}/complete`);
      setMsg("Ödeme başarıyla tamamlandı!");
      setPayModal(null);
      load();
    } catch (e) { setMsg(e.response?.data?.detail || "Hata oluştu"); }
    finally { setProcessing(false); }
  };

  if (loading) return <Layout><div className="page-center"><span className="loading-spin" /></div></Layout>;

  return (
    <Layout>
      <div className="page-header"><h1 className="page-title">💳 Ödemeler</h1></div>

      {msg && <div className="alert" style={{ marginBottom: "1rem", padding: "0.75rem 1rem", background: msg.includes("başarı") ? "#d1fae5" : "#fee2e2", borderRadius: "0.5rem", fontSize: "0.9rem" }}>{msg}</div>}

      {unpaidMatches.length > 0 && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ marginBottom: "1rem" }}>⏳ Ödenmemiş Eşleşmeler</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Referans</th><th>Tutar</th><th>Durum</th><th>İşlem</th></tr></thead>
              <tbody>
                {unpaidMatches.map((m) => (
                  <tr key={m.id}>
                    <td><strong>{m.reference_code}</strong></td>
                    <td>₺{m.fee_amount?.toFixed(2)}</td>
                    <td><span className="status-chip status-pending">Ödenmemiş</span></td>
                    <td><button className="btn-primary btn-sm" onClick={() => initiatePayment(m.id)} disabled={processing}>Ödeme Yap</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginBottom: "1rem" }}>📋 Ödeme Geçmişi</h3>
        {payments.length === 0 ? (
          <div className="empty-state"><div className="empty-state-icon">💳</div><div className="empty-state-title">Henüz ödeme yok</div></div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Referans</th><th>Tutar</th><th>Yöntem</th><th>Durum</th><th>Fatura</th><th>Tarih</th></tr></thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td><strong>{p.reference_code}</strong></td>
                    <td>₺{p.amount?.toFixed(2)}</td>
                    <td>{p.method === "credit_card" ? "Kredi Kartı" : p.method}</td>
                    <td><span className={`status-chip status-${p.status === "completed" ? "accepted" : p.status}`}>{p.status === "completed" ? "Tamamlandı" : p.status === "pending" ? "Beklemede" : p.status}</span></td>
                    <td>{p.invoice_id ? <Link to="/invoices" style={{ color: "#2563eb" }}>Görüntüle</Link> : "-"}</td>
                    <td>{new Date(p.created_at).toLocaleDateString("tr-TR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pay Modal */}
      <Modal open={!!payModal} onClose={() => setPayModal(null)} title="Ödeme Onayı" size="sm">
        {payModal && (
          <div>
            <div style={{ textAlign: "center", padding: "1.5rem 0" }}>
              <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>💳</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#1a3a2a" }}>₺{payModal.amount?.toFixed(2)}</div>
              <div style={{ color: "#6b7c93", margin: "0.5rem 0" }}>Ref: {payModal.reference_code}</div>
              <p style={{ color: "#6b7c93", fontSize: "0.85rem" }}>Bu demo ödemedir. "Ödemeyi Tamamla" butonuna basarak mock ödeme yapabilirsiniz.</p>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center" }}>
              <button className="btn-ghost" onClick={() => setPayModal(null)}>İptal</button>
              <button className="btn-primary" onClick={() => completePayment(payModal.id)} disabled={processing}>{processing ? "İşleniyor..." : "Ödemeyi Tamamla"}</button>
            </div>
          </div>
        )}
      </Modal>
    </Layout>
  );
};

// =============================================================================
// ── Invoices Page ─────────────────────────────────────────────────────────────
// =============================================================================
const InvoicesPage = () => {
  const [invoices, setInvoices] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [detail, setDetail] = React.useState(null);

  React.useEffect(() => {
    const load = async () => {
      try { const res = await axios.get("/invoices"); setInvoices(res.data); }
      catch {} finally { setLoading(false); }
    };
    load();
  }, []);

  if (loading) return <Layout><div className="page-center"><span className="loading-spin" /></div></Layout>;

  return (
    <Layout>
      <div className="page-header"><h1 className="page-title">🧾 Faturalar</h1></div>
      {invoices.length === 0 ? (
        <div className="empty-state"><div className="empty-state-icon">🧾</div><div className="empty-state-title">Henüz fatura yok</div><div className="empty-state-sub">Ödeme tamamlandığında faturalar burada görünecek.</div></div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Fatura No</th><th>Ara Toplam</th><th>KDV (%20)</th><th>Toplam</th><th>Durum</th><th>Tarih</th><th>Detay</th></tr></thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td><strong>{inv.invoice_number}</strong></td>
                    <td>₺{inv.subtotal?.toFixed(2)}</td>
                    <td>₺{inv.tax_amount?.toFixed(2)}</td>
                    <td style={{ fontWeight: 600 }}>₺{inv.total?.toFixed(2)}</td>
                    <td><span className={`status-chip status-${inv.status === "issued" ? "pending" : "accepted"}`}>{inv.status === "issued" ? "Kesildi" : "Ödendi"}</span></td>
                    <td>{new Date(inv.created_at).toLocaleDateString("tr-TR")}</td>
                    <td><button className="btn-ghost btn-sm" onClick={() => setDetail(inv)}>Detay</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal open={!!detail} onClose={() => setDetail(null)} title={`Fatura: ${detail?.invoice_number}`} size="lg">
        {detail && (
          <div>
            <div className="grid-2" style={{ gap: "1rem", marginBottom: "1.5rem" }}>
              <div><strong>Otel:</strong> {detail.hotel_name}</div>
              <div><strong>Adres:</strong> {detail.hotel_address}</div>
              <div><strong>Fatura No:</strong> {detail.invoice_number}</div>
              <div><strong>Tarih:</strong> {new Date(detail.created_at).toLocaleDateString("tr-TR")}</div>
            </div>
            <div className="table-wrap" style={{ marginBottom: "1rem" }}>
              <table>
                <thead><tr><th>Açıklama</th><th>Miktar</th><th>Birim Fiyat</th><th>Toplam</th></tr></thead>
                <tbody>
                  {detail.items?.map((item, i) => (
                    <tr key={i}><td>{item.description}</td><td>{item.quantity}</td><td>₺{item.unit_price?.toFixed(2)}</td><td>₺{item.total?.toFixed(2)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ textAlign: "right", borderTop: "2px solid #e5e7eb", paddingTop: "1rem" }}>
              <div>Ara Toplam: ₺{detail.subtotal?.toFixed(2)}</div>
              <div>KDV (%{(detail.tax_rate * 100).toFixed(0)}): ₺{detail.tax_amount?.toFixed(2)}</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#1a3a2a", marginTop: "0.5rem" }}>Genel Toplam: ₺{detail.total?.toFixed(2)}</div>
            </div>
          </div>
        )}
      </Modal>
    </Layout>
  );
};

// =============================================================================
// ── Subscription Page ─────────────────────────────────────────────────────────
// =============================================================================
const SubscriptionPage = () => {
  const [plans, setPlans] = React.useState([]);
  const [mySub, setMySub] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [msg, setMsg] = React.useState("");
  const [processing, setProcessing] = React.useState(false);

  const load = async () => {
    try {
      const [pRes, sRes] = await Promise.all([
        axios.get("/subscriptions/plans"),
        axios.get("/subscriptions/my"),
      ]);
      setPlans(pRes.data);
      setMySub(sRes.data);
    } catch {} finally { setLoading(false); }
  };

  React.useEffect(() => { load(); }, []);

  const subscribe = async (planId, cycle) => {
    setProcessing(true); setMsg("");
    try {
      await axios.post("/subscriptions/subscribe", { plan_id: planId, billing_cycle: cycle });
      setMsg("Abonelik başarıyla aktifleştirildi!");
      load();
    } catch (e) { setMsg(e.response?.data?.detail || "Hata"); }
    finally { setProcessing(false); }
  };

  const cancelSub = async () => {
    if (!window.confirm("Aboneliğinizi iptal etmek istediğinize emin misiniz?")) return;
    try {
      await axios.post("/subscriptions/cancel");
      setMsg("Abonelik iptal edildi.");
      load();
    } catch (e) { setMsg(e.response?.data?.detail || "Hata"); }
  };

  if (loading) return <Layout><div className="page-center"><span className="loading-spin" /></div></Layout>;

  return (
    <Layout>
      <div className="page-header"><h1 className="page-title">⭐ Abonelik Planları</h1></div>

      {msg && <div className="alert" style={{ marginBottom: "1rem", padding: "0.75rem 1rem", background: msg.includes("başarı") || msg.includes("aktif") ? "#d1fae5" : "#fef3c7", borderRadius: "0.5rem" }}>{msg}</div>}

      {mySub && (
        <div className="card" style={{ marginBottom: "1.5rem", borderLeft: "4px solid #10b981" }}>
          <h3>📌 Aktif Planınız: {mySub.plan_name || "Ücretsiz"}</h3>
          <div style={{ display: "flex", gap: "2rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
            <div><strong>Eşleşme Limiti:</strong> {mySub.max_matches === -1 ? "Sınırsız" : `${mySub.matches_used || 0} / ${mySub.max_matches}`}</div>
            {mySub.expires_at && <div><strong>Bitiş:</strong> {new Date(mySub.expires_at).toLocaleDateString("tr-TR")}</div>}
            {mySub.plan_id && mySub.plan_id !== "free" && (
              <button className="btn-ghost btn-sm" onClick={cancelSub} style={{ color: "#ef4444" }}>İptal Et</button>
            )}
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1.5rem" }}>
        {plans.map((plan) => (
          <div key={plan.id} className="card" style={{ border: mySub?.plan_id === plan.id ? "2px solid #10b981" : "1px solid #e5e7eb", position: "relative" }}>
            {mySub?.plan_id === plan.id && <div style={{ position: "absolute", top: "-10px", right: "10px", background: "#10b981", color: "white", padding: "2px 10px", borderRadius: "12px", fontSize: "0.75rem" }}>Aktif</div>}
            <h3 style={{ marginBottom: "0.5rem" }}>{plan.name}</h3>
            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#1a3a2a" }}>₺{plan.price_monthly}<span style={{ fontSize: "0.8rem", fontWeight: 400, color: "#6b7c93" }}>/ay</span></div>
            {plan.price_yearly > 0 && <div style={{ fontSize: "0.85rem", color: "#6b7c93" }}>Yıllık: ₺{plan.price_yearly}/yıl</div>}
            <div style={{ margin: "1rem 0", fontSize: "0.85rem", color: "#374151" }}>
              <div>📊 {plan.max_matches_per_month === -1 ? "Sınırsız" : `${plan.max_matches_per_month}`} eşleşme/ay</div>
              {plan.features.map((f, i) => <div key={i} style={{ marginTop: "0.25rem" }}>✓ {f}</div>)}
            </div>
            {mySub?.plan_id !== plan.id && (
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button className="btn-primary btn-sm" onClick={() => subscribe(plan.id, "monthly")} disabled={processing}>Aylık Seç</button>
                {plan.price_yearly > 0 && <button className="btn-ghost btn-sm" onClick={() => subscribe(plan.id, "yearly")} disabled={processing}>Yıllık Seç</button>}
              </div>
            )}
          </div>
        ))}
      </div>
    </Layout>
  );
};

// =============================================================================
// ── Notifications Page ────────────────────────────────────────────────────────
// =============================================================================
const NotificationsPage = () => {
  const [notifications, setNotifications] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [filter, setFilter] = React.useState("all");

  const load = async () => {
    try {
      const params = filter === "unread" ? { unread_only: true } : {};
      const res = await axios.get("/notifications", { params });
      setNotifications(res.data);
    } catch {} finally { setLoading(false); }
  };

  React.useEffect(() => { load(); }, [filter]);

  const markRead = async (id) => {
    try {
      await axios.put(`/notifications/${id}/read`);
      setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
    } catch {}
  };

  const markAllRead = async () => {
    try {
      await axios.put("/notifications/read-all");
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {}
  };

  const typeIcon = (t) => {
    const map = { request_received: "📋", match_created: "🤝", payment_completed: "💳", alternative_offered: "🔄", subscription_created: "⭐", kvkk_request: "🔒" };
    return map[t] || "🔔";
  };

  if (loading) return <Layout><div className="page-center"><span className="loading-spin" /></div></Layout>;

  return (
    <Layout>
      <div className="page-header">
        <h1 className="page-title">🔔 Bildirimler</h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <select value={filter} onChange={(e) => setFilter(e.target.value)} style={{ padding: "0.4rem", borderRadius: "0.4rem", border: "1px solid #d1d5db" }}>
            <option value="all">Tümü</option>
            <option value="unread">Okunmamış</option>
          </select>
          <button className="btn-ghost btn-sm" onClick={markAllRead}>Tümünü Okundu Yap</button>
        </div>
      </div>

      {notifications.length === 0 ? (
        <div className="empty-state"><div className="empty-state-icon">🔔</div><div className="empty-state-title">Bildirim yok</div></div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {notifications.map((n) => (
            <div key={n.id} className="card" style={{ padding: "1rem", display: "flex", gap: "1rem", alignItems: "flex-start", opacity: n.is_read ? 0.7 : 1, borderLeft: n.is_read ? "3px solid #e5e7eb" : "3px solid #2563eb", cursor: "pointer" }} onClick={() => !n.is_read && markRead(n.id)}>
              <span style={{ fontSize: "1.5rem" }}>{typeIcon(n.type)}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{n.title}</div>
                <div style={{ color: "#6b7c93", fontSize: "0.85rem" }}>{n.message}</div>
                <div style={{ color: "#9ca3af", fontSize: "0.75rem", marginTop: "0.25rem" }}>{new Date(n.created_at).toLocaleString("tr-TR")}</div>
              </div>
              {!n.is_read && <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#2563eb", flexShrink: 0, marginTop: "6px" }} />}
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
};

// ── App Router ────────────────────────────────────────────────────────────────
const App = () => (
  <AuthProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="/listings" element={<ProtectedRoute><ListingsPage /></ProtectedRoute>} />
        <Route path="/listings/:id" element={<ProtectedRoute><ListingDetailPage /></ProtectedRoute>} />
        <Route path="/availability" element={<ProtectedRoute><AvailabilityPage /></ProtectedRoute>} />
        <Route path="/requests" element={<ProtectedRoute><RequestsPage /></ProtectedRoute>} />
        <Route path="/matches" element={<ProtectedRoute><MatchesPage /></ProtectedRoute>} />
        <Route path="/matches/:id" element={<ProtectedRoute><MatchDetailPage /></ProtectedRoute>} />
        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
        <Route path="/inventory" element={<ProtectedRoute><InventoryPage /></ProtectedRoute>} />
        <Route path="/pricing" element={<ProtectedRoute><PricingPage /></ProtectedRoute>} />
        <Route path="/performance" element={<ProtectedRoute><PerformancePage /></ProtectedRoute>} />
        <Route path="/payments" element={<ProtectedRoute><PaymentsPage /></ProtectedRoute>} />
        <Route path="/invoices" element={<ProtectedRoute><InvoicesPage /></ProtectedRoute>} />
        <Route path="/subscription" element={<ProtectedRoute><SubscriptionPage /></ProtectedRoute>} />
        <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  </AuthProvider>
);

export default App;
