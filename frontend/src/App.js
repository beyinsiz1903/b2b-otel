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

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-brand">
          <div className="shell-brand-icon">🏨</div>
          CapX Sapanca-Kartepe
        </div>
        <div className="shell-right">
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
          <Link to="/requests" className={isActive("/requests")} data-testid="nav-requests">
            📋 Talepler
          </Link>
          <Link to="/matches" className={isActive("/matches")} data-testid="nav-matches">
            🤝 Eşleşmeler
          </Link>
          <div className="shell-nav-divider" />
          <div className="shell-nav-label">Hesap</div>
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
    } catch {
      setError("Giriş başarısız. E-posta veya şifre hatalı.");
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
  const [error, setError] = React.useState("");
  const [success, setSuccess] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await axios.post("/auth/register", form);
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
        <div className="auth-panel" style={{ textAlign: "center" }}>
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🎉</div>
          <h2 style={{ color: "#1a3a2a", marginBottom: "0.5rem" }}>Kayıt Başarılı!</h2>
          <p style={{ color: "#6b7c93", marginBottom: "1.5rem" }}>
            Hesabınız oluşturuldu. Şimdi giriş yapabilirsiniz.
          </p>
          <Link to="/login" className="btn-primary">Giriş Yap</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-layout">
      <div className="auth-panel" style={{ maxWidth: 640 }}>
        <div className="auth-logo">
          <div className="auth-logo-icon">🏨</div>
          <span style={{ fontWeight: 700, fontSize: "1.1rem", color: "#1a3a2a" }}>CapX</span>
        </div>
        <h1 className="auth-title">Otel Kaydı</h1>
        <p className="auth-subtitle">Tüm alanları eksiksiz doldurun.</p>
        <form onSubmit={handleSubmit} className="auth-form" data-testid="register-form">
          <div className="grid-2">
            <label className="field">
              <span>Otel Adı</span>
              <input name="name" value={form.name} onChange={onChange} placeholder="Örn: Sapanca Bungalov" required />
            </label>
            <label className="field">
              <span>Bölge</span>
              <select name="region" value={form.region} onChange={onChange}>
                <option value="Sapanca">Sapanca</option>
                <option value="Kartepe">Kartepe</option>
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
          {error && <div className="error">{error}</div>}
          <button className="btn-primary w-full" type="submit" disabled={loading} data-testid="register-submit">
            {loading ? <><span className="loading-spin" /> Kaydediliyor...</> : "Kaydı Tamamla"}
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
    price_max: "",
    avail_status: "",
    hide_expired: true,
  });
  const navigate = useNavigate();

  const load = async (f) => {
    setLoading(true);
    try {
      const params = {};
      if (f.region) params.region = f.region;
      if (f.concept) params.concept = f.concept;
      if (f.pax_min) params.pax_min = parseInt(f.pax_min);
      if (f.price_max) params.price_max = parseFloat(f.price_max);
      if (f.avail_status) params.avail_status = f.avail_status;
      params.hide_expired = f.hide_expired;
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
    const fresh = { region: "", concept: "", pax_min: "", price_max: "", avail_status: "", hide_expired: true };
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
                <span>Min. Kişi Sayısı</span>
                <input
                  type="number"
                  min="1"
                  value={filters.pax_min}
                  onChange={(e) => setFilters({ ...filters, pax_min: e.target.value })}
                  placeholder="Örn: 2"
                />
              </label>
              <label className="field">
                <span>Maks. Fiyat (TL/gece)</span>
                <input
                  type="number"
                  value={filters.price_max}
                  onChange={(e) => setFilters({ ...filters, price_max: e.target.value })}
                  placeholder="Örn: 10000"
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
    template_id: "",
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

// ── Profile Page ──────────────────────────────────────────────────────────────
const ProfilePage = () => {
  const { hotel, reload } = useAuth();
  const [tab, setTab] = React.useState("profile");
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
  const [success, setSuccess] = React.useState("");
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
        </div>
      </div>
    </Layout>
  );
};

// ── Reports Page ──────────────────────────────────────────────────────────────
const ReportsPage = () => {
  const [stats, setStats] = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get("/stats");
        setStats(res.data);
      } catch {
        setStats(null);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return <Layout><div className="page-center" style={{ height: 300 }}><span className="loading-spin" /></div></Layout>;
  }

  if (!stats) {
    return <Layout><div className="error">İstatistikler yüklenemedi.</div></Layout>;
  }

  // Monthly data
  const allMonthKeys = Object.keys({ ...stats.monthly_matches, ...stats.monthly_fees }).sort();
  const last6 = allMonthKeys.slice(-6);
  const maxMatches = Math.max(...last6.map((k) => stats.monthly_matches[k] || 0), 1);

  // Region data
  const regions = Object.entries(stats.region_counts || {});
  const maxRegion = Math.max(...regions.map(([, v]) => v), 1);

  return (
    <Layout>
      <h1 className="page-title">📈 Raporlar &amp; Analitik</h1>

      <div className="cards-row" style={{ marginBottom: "2rem" }}>
        <div className="kpi-card kpi-green">
          <span>Toplam Eşleşme</span>
          <strong>{stats.total_matches}</strong>
        </div>
        <div className="kpi-card kpi-blue">
          <span>Toplam Hizmet Bedeli</span>
          <strong style={{ fontSize: "1.3rem" }}>{stats.total_fees?.toLocaleString("tr-TR")} TL</strong>
        </div>
        <div className="kpi-card kpi-orange">
          <span>Gönderilen Kabul %</span>
          <strong>{stats.acceptance_rate_outgoing}%</strong>
        </div>
        <div className="kpi-card">
          <span>Gelen Kabul %</span>
          <strong>{stats.acceptance_rate_incoming}%</strong>
        </div>
      </div>

      <div className="reports-grid">
        {/* Monthly Matches Chart */}
        <div className="report-card">
          <h3>📅 Aylık Eşleşmeler</h3>
          {last6.length === 0 ? (
            <div className="text-muted text-sm">Henüz veri yok</div>
          ) : (
            <div className="bar-chart">
              {last6.map((month) => {
                const count = stats.monthly_matches[month] || 0;
                const pct = Math.max((count / maxMatches) * 100, 2);
                return (
                  <div key={month} className="bar-row">
                    <div className="bar-label">{month.slice(5)}/{month.slice(2, 4)}</div>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${pct}%` }}>
                        {count > 0 && <span className="bar-value">{count}</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Monthly Fees Chart */}
        <div className="report-card">
          <h3>💰 Aylık Hizmet Bedeli (TL)</h3>
          {last6.length === 0 ? (
            <div className="text-muted text-sm">Henüz veri yok</div>
          ) : (
            <div className="bar-chart">
              {last6.map((month) => {
                const fee = stats.monthly_fees[month] || 0;
                const maxFee = Math.max(...last6.map((k) => stats.monthly_fees[k] || 0), 1);
                const pct = Math.max((fee / maxFee) * 100, 2);
                return (
                  <div key={month} className="bar-row">
                    <div className="bar-label">{month.slice(5)}/{month.slice(2, 4)}</div>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${pct}%`, background: "linear-gradient(90deg, #d97706, #fbbf24)" }}>
                        {fee > 0 && <span className="bar-value">{fee.toLocaleString("tr-TR")}</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Request Stats */}
        <div className="report-card">
          <h3>📋 Talep İstatistikleri</h3>
          <div className="stats-list">
            <div className="stats-row">
              <span className="stats-row-label">Toplam Gönderilen</span>
              <span className="stats-row-value">{stats.total_outgoing_requests}</span>
            </div>
            <div className="stats-row">
              <span className="stats-row-label">Kabul Edilen</span>
              <span className="stats-row-value text-green">{stats.accepted_outgoing}</span>
            </div>
            <div className="stats-row">
              <span className="stats-row-label">Toplam Gelen</span>
              <span className="stats-row-value">{stats.total_incoming_requests}</span>
            </div>
            <div className="stats-row">
              <span className="stats-row-label">Kabul Ettiğim</span>
              <span className="stats-row-value text-green">{stats.accepted_incoming}</span>
            </div>
            <div className="stats-row">
              <span className="stats-row-label">Bekleyen Gelen</span>
              <span className="stats-row-value text-red">{stats.pending_incoming}</span>
            </div>
          </div>
        </div>

        {/* Region Breakdown */}
        <div className="report-card">
          <h3>📍 Bölgesel Eşleşmeler</h3>
          {regions.length === 0 ? (
            <div className="text-muted text-sm">Henüz veri yok</div>
          ) : (
            <div className="bar-chart">
              {regions.map(([region, count]) => {
                const pct = Math.max((count / maxRegion) * 100, 2);
                return (
                  <div key={region} className="bar-row">
                    <div className="bar-label" style={{ width: 80 }}>{region}</div>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${pct}%`, background: "linear-gradient(90deg, #1d4ed8, #60a5fa)" }}>
                        <span className="bar-value">{count}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Listing Stats */}
        <div className="report-card">
          <h3>🏠 İlan Durumu</h3>
          <div className="stats-list">
            <div className="stats-row">
              <span className="stats-row-label">Aktif İlanlar</span>
              <span className="stats-row-value text-green">{stats.active_listings}</span>
            </div>
            <div className="stats-row">
              <span className="stats-row-label">Süresi Geçmiş</span>
              <span className="stats-row-value text-muted">{stats.expired_listings}</span>
            </div>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <div style={{ fontSize: "0.8rem", color: "#6b7c93", marginBottom: "0.5rem" }}>Gönderilen Kabul Oranı</div>
            <div className="rate-indicator">
              <div className="rate-bar-outer">
                <div className="rate-bar-inner" style={{ width: `${stats.acceptance_rate_outgoing}%` }} />
              </div>
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#2e6b57" }}>{stats.acceptance_rate_outgoing}%</span>
            </div>
          </div>
        </div>

        {/* This month summary */}
        <div className="report-card">
          <h3>🗓️ Bu Ay Özeti</h3>
          <div className="stats-list">
            <div className="stats-row">
              <span className="stats-row-label">Eşleşme</span>
              <span className="stats-row-value">{stats.this_month_matches}</span>
            </div>
            <div className="stats-row">
              <span className="stats-row-label">Hizmet Bedeli</span>
              <span className="stats-row-value">{stats.this_month_fees?.toLocaleString("tr-TR")} TL</span>
            </div>
            <div className="stats-row">
              <span className="stats-row-label">Toplam Birikimli</span>
              <span className="stats-row-value">{stats.total_fees?.toLocaleString("tr-TR")} TL</span>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

// ── Admin Page ────────────────────────────────────────────────────────────────
const AdminPage = () => {
  const { hotel } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = React.useState("overview");
  const [overview, setOverview] = React.useState(null);
  const [hotels, setHotels] = React.useState([]);
  const [matches, setMatches] = React.useState([]);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (!hotel?.is_admin) {
      navigate("/dashboard");
    }
  }, [hotel, navigate]);

  React.useEffect(() => {
    if (tab === "overview") loadOverview();
    if (tab === "hotels") loadHotels();
    if (tab === "matches") loadAdminMatches();
  }, [tab]);

  const loadOverview = async () => {
    setLoading(true);
    try {
      const res = await axios.get("/admin/overview");
      setOverview(res.data);
    } catch {
      setOverview(null);
    } finally {
      setLoading(false);
    }
  };

  const loadHotels = async () => {
    setLoading(true);
    try {
      const res = await axios.get("/admin/hotels");
      setHotels(res.data);
    } catch {
      setHotels([]);
    } finally {
      setLoading(false);
    }
  };

  const loadAdminMatches = async () => {
    setLoading(true);
    try {
      const res = await axios.get("/admin/matches");
      setMatches(res.data);
    } catch {
      setMatches([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleAdmin = async (hotelId) => {
    try {
      await axios.put(`/admin/hotels/${hotelId}/toggle-admin`);
      await loadHotels();
    } catch (err) {
      alert(err.response?.data?.detail || "İşlem başarısız.");
    }
  };

  const updateFeeStatus = async (matchId, status) => {
    try {
      await axios.put(`/admin/matches/${matchId}/fee-status`, { fee_status: status });
      await loadAdminMatches();
    } catch (err) {
      alert(err.response?.data?.detail || "İşlem başarısız.");
    }
  };

  return (
    <Layout>
      <div className="flex items-center gap-2" style={{ marginBottom: "1.5rem" }}>
        <h1 className="page-title" style={{ margin: 0 }}>⚙️ Admin Paneli</h1>
        <span className="admin-badge">Platform Yöneticisi</span>
      </div>

      <div className="admin-tabs">
        <div className={`admin-tab ${tab === "overview" ? "active" : ""}`} onClick={() => setTab("overview")}>
          📊 Genel Bakış
        </div>
        <div className={`admin-tab ${tab === "hotels" ? "active" : ""}`} onClick={() => setTab("hotels")}>
          🏨 Oteller ({hotels.length})
        </div>
        <div className={`admin-tab ${tab === "matches" ? "active" : ""}`} onClick={() => setTab("matches")}>
          🤝 Tüm Eşleşmeler
        </div>
      </div>

      {loading ? (
        <div className="page-center" style={{ height: 200 }}><span className="loading-spin" /></div>
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
                  <td>{h.listing_count}</td>
                  <td>{h.match_count}</td>
                  <td style={{ fontSize: "0.8rem", color: "#6b7c93" }}>
                    {h.created_at ? new Date(h.created_at).toLocaleDateString("tr-TR") : "-"}
                  </td>
                  <td>
                    {h.is_admin ? <span className="admin-badge">Admin</span> : <span className="text-muted">-</span>}
                  </td>
                  <td>
                    <button
                      className={`btn-sm ${h.is_admin ? "btn-danger" : "btn-secondary"}`}
                      onClick={() => toggleAdmin(h.id)}
                      title={h.is_admin ? "Admin yetkisini kaldır" : "Admin yap"}
                    >
                      {h.is_admin ? "Admin Kaldır" : "Admin Yap"}
                    </button>
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
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  </AuthProvider>
);

export default App;
