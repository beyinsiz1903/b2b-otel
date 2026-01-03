import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams, Link, useLocation } from "react-router-dom";
import axios from "axios";
import "@/App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Simple auth utilities (JWT in localStorage)
const getToken = () => localStorage.getItem("token");
const setToken = (t) => localStorage.setItem("token", t || "");
const clearToken = () => localStorage.removeItem("token");

axios.defaults.baseURL = API;
axios.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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

  React.useEffect(() => {
    loadMe();
  }, []);

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

  const logout = () => {
    clearToken();
    setHotel(null);
  };

  const value = { hotel, login, logout };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

const useAuth = () => React.useContext(AuthContext);

const ProtectedRoute = ({ children }) => {
  const { hotel } = useAuth();
  if (!getToken()) return <Navigate to="/login" replace />;
  if (!hotel) return <div className="page-center">Loading...</div>;
  return children;
};

// --- Pages -----------------------------------------------------------------

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
      setError("Giriş başarısız. Bilgileri kontrol edin.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-panel">
        <h1 className="auth-title">Kapsite Eşleştirme Girişi</h1>
        <p className="auth-subtitle">Yalnızca Sapanca / Kartepe otelleri için B2B platform.</p>
        <form onSubmit={handleSubmit} className="auth-form" data-testid="login-form">
          <label className="field">
            <span>E-posta</span>
            <input
              data-testid="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
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
            {loading ? "Giriş yapılıyor..." : "Giriş Yap"}
          </button>
        </form>
      </div>
    </div>
  );
};

const RegisterPage = () => {
  const [form, setForm] = React.useState({
    name: "",
    region: "Sapanca",
    micro_location: "",
    concept: "",
    address: "",
    phone: "",
    whatsapp: "",
    website: "",
    contact_person: "",
    email: "",
    password: "",
  });
  const [error, setError] = React.useState("");
  const [success, setSuccess] = React.useState(false);

  const onChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await axios.post("/auth/register", form);
      setSuccess(true);
    } catch (err) {
      setError("Kayıt başarısız. Bilgileri kontrol edin.");
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-panel">
        <h1 className="auth-title">Otel Kaydı</h1>
        <form onSubmit={handleSubmit} className="auth-form" data-testid="register-form">
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
              <input name="micro_location" value={form.micro_location} onChange={onChange} required />
            </label>
            <label className="field">
              <span>Kavram / Konsept</span>
              <input name="concept" value={form.concept} onChange={onChange} required />
            </label>
          </div>
          <label className="field">
            <span>Adres</span>
            <input name="address" value={form.address} onChange={onChange} required />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Telefon</span>
              <input name="phone" value={form.phone} onChange={onChange} required />
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
          <div className="grid-2">
            <label className="field">
              <span>E-posta</span>
              <input type="email" name="email" value={form.email} onChange={onChange} required />
            </label>
            <label className="field">
              <span>Şifre</span>
              <input type="password" name="password" value={form.password} onChange={onChange} required />
            </label>
          </div>
          {error && <div className="error">{error}</div>}
          {success && <div className="success">Kayıt başarılı. Giriş yapabilirsiniz.</div>}
          <button className="btn-primary w-full" type="submit" data-testid="register-submit">
            Kaydı Tamamla
          </button>
        </form>
      </div>
    </div>
  );
};

const Layout = ({ children }) => {
  const { hotel, logout } = useAuth();
  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-brand">CapX Sapanca-Kartepe</div>
        <div className="shell-right">
          <span className="shell-user">{hotel?.name}</span>
          <button className="btn-ghost" onClick={logout} data-testid="logout-button">
            Çıkış
          </button>
        </div>
      </header>
      <div className="shell-main">
        <nav className="shell-nav">
          <Link to="/dashboard" data-testid="nav-dashboard">Panel</Link>
          <Link to="/listings" data-testid="nav-listings">Anonim Kapasiteler</Link>
          <Link to="/availability" data-testid="nav-availability">Kendi Kapasitem</Link>
          <Link to="/requests" data-testid="nav-requests">Talepler</Link>
          <Link to="/matches" data-testid="nav-matches">Eşleşmeler</Link>
        </nav>
        <main className="shell-content">{children}</main>
      </div>
    </div>
  );
};

const DashboardPage = () => {
  const [stats, setStats] = React.useState(null);

  React.useEffect(() => {
    const load = async () => {
      try {
        const [outRes, inRes, matchesRes] = await Promise.all([
          axios.get("/requests/outgoing"),
          axios.get("/requests/incoming"),
          axios.get("/matches"),
        ]);

        const now = new Date();
        const currentMonth = now.getMonth();
        const currentYear = now.getFullYear();
        let monthlyMatchCount = 0;
        let monthlyFeeTotal = 0;

        matchesRes.data.forEach((m) => {
          if (!m.accepted_at) return;
          const d = new Date(m.accepted_at);
          if (d.getMonth() === currentMonth && d.getFullYear() === currentYear) {
            monthlyMatchCount += 1;
            monthlyFeeTotal += m.fee_amount || 0;
          }
        });

        setStats({
          outgoing: outRes.data.length,
          incoming: inRes.data.length,
          matches: matchesRes.data.length,
          monthlyMatchCount,
          monthlyFeeTotal,
        });
      } catch {
        setStats({ outgoing: 0, incoming: 0, matches: 0, monthlyMatchCount: 0, monthlyFeeTotal: 0 });
      }
    };
    load();
  }, []);

  return (
    <Layout>
      <h1 className="page-title">Genel Bakış</h1>
      <div className="cards-row">
        <div className="kpi-card" data-testid="kpi-outgoing">
          <span>Gönderilen Talepler</span>
          <strong>{stats?.outgoing ?? "-"}</strong>
        </div>
        <div className="kpi-card" data-testid="kpi-incoming">
          <span>Gelen Talepler</span>
          <strong>{stats?.incoming ?? "-"}</strong>
        </div>
        <div className="kpi-card" data-testid="kpi-matches">
          <span>Onaylanmış Eşleşmeler</span>
          <strong>{stats?.matches ?? "-"}</strong>
        </div>
        <div className="kpi-card" data-testid="kpi-monthly-fee">
          <span>Bu Ayki Eşleşmeler / Hizmet Bedeli</span>
          <strong>
            {stats ? `${stats.monthlyMatchCount} eşleşme / ${stats.monthlyFeeTotal} TL` : "-"}
          </strong>
        </div>
      </div>
    </Layout>
  );
};

const ListingsPage = () => {
  const [listings, setListings] = React.useState([]);
  const navigate = useNavigate();

  const load = async () => {
    const res = await axios.get("/listings");
    setListings(res.data);
  };

  React.useEffect(() => {
    load();
  }, []);

  return (
    <Layout>
      <h1 className="page-title">Anonim Kapasite Listesi</h1>
      <div className="cards-grid">
        {listings.map((l) => (
          <div
            className="listing-card listing-card-clickable"
            key={l.id}
            data-testid="listing-card"
            onClick={() => navigate(`/listings/${l.id}`)}
          >
            {l.image_urls && l.image_urls.length > 0 && (
              <div className="listing-image-wrapper">
                <img src={l.image_urls[0]} alt="Kapasite görseli" className="listing-image" />
              </div>
            )}
            <div className="listing-header">
              <span className="badge-region">{l.region} / {l.micro_location}</span>
              <span className={`status-chip status-${l.availability_status}`}>
                {l.availability_status}
              </span>
            </div>
            <div className="listing-body">
              <div>Konsept: {l.concept}</div>
              <div>Kapasite: {l.capacity_label} ({l.pax} kişi)</div>
              <div>
                Tarih: {new Date(l.date_start).toLocaleDateString()} - {" "}
                {new Date(l.date_end).toLocaleDateString()} ({l.nights} gece)
              </div>
              <div>Fiyat: {l.price_min} TL / gece</div>
              {l.features && l.features.length > 0 && (
                <div className="listing-features">
                  {l.features.slice(0, 4).map((f) => (
                    <span key={f} className="feature-badge">
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </div>
            {l.is_locked && (
              <div className="locked-badge">Bu kapasite şu an kilitli</div>
            )}
          </div>
        ))}
      </div>
    </Layout>
  );
};

const AvailabilityPage = () => {
  const [form, setForm] = React.useState({
    region: "Sapanca",
    micro_location: "",
    concept: "",
    capacity_label: "2+1",
    pax: 4,
    date_start: "",
    date_end: "",
    nights: 1,
    price_min: 0,
    price_max: 0,
    availability_status: "available",
    image_urls_raw: "",
    features_raw: "",
  });
  const [mine, setMine] = React.useState([]);

  const onChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const loadMine = async () => {
    const res = await axios.get("/listings", { params: { mine: true } });
    setMine(res.data);
  };

  React.useEffect(() => {
    loadMine();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();

    const image_urls = form.image_urls_raw
      ? form.image_urls_raw
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      : [];

    const features = form.features_raw
      ? form.features_raw
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      : [];

    const price = Number(form.price_min);

    await axios.post("/listings", {
      region: form.region,
      micro_location: form.micro_location,
      concept: form.concept,
      capacity_label: form.capacity_label,
      pax: Number(form.pax),
      date_start: new Date(form.date_start).toISOString(),
      date_end: new Date(form.date_end).toISOString(),
      nights: Number(form.nights),
      price_min: price,
      price_max: price,
      availability_status: form.availability_status,
      image_urls,
      features,
    });
    await loadMine();
  };

  return (
    <Layout>
      <h1 className="page-title">Kendi Kapasitelerim</h1>
      <div className="info-banner">
        <strong>🔒 Anonim ilan</strong>
        Bu ilanlar anonim görünür. Otel adı/iletişim bilgisi <strong>eşleşme olmadan açılmaz</strong>.
        Lütfen görsellerde isim/logo kullanmayın.
      </div>
      <form className="availability-form" onSubmit={handleSubmit} data-testid="availability-form">
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
            <input name="micro_location" value={form.micro_location} onChange={onChange} required />
          </label>
          <label className="field">
            <span>Konsept</span>
            <input name="concept" value={form.concept} onChange={onChange} required />
            <span className="field-help">
              Misafirin beklentisini belirler. Örn: Bungalov, Butik, Dağ evi, Resort.
            </span>
          </label>
        </div>
        <div className="grid-3">
          <label className="field">
            <span>Kapasite Label</span>
            <input name="capacity_label" value={form.capacity_label} onChange={onChange} />
          </label>
          <label className="field">
            <span>Kişi Sayısı</span>
            <input name="pax" type="number" value={form.pax} onChange={onChange} />
            <span className="field-help">
              Pax misafirin sayısıdır. Kartlar bu bilgiye göre filtrelenir; yanlış girilirse talep kaçırırsınız.
            </span>
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
            <span>Başlangıç Tarihi</span>
            <input name="date_start" type="date" value={form.date_start} onChange={onChange} required />
          </label>
          <label className="field">
            <span>Bitiş Tarihi</span>
            <input name="date_end" type="date" value={form.date_end} onChange={onChange} required />
            <span className="field-help">
              Mümkünse net tarih girin. ‘Alternatif’ durumlarda karşı teklif akışıyla farklı tarih sunabilirsiniz.
            </span>
          </label>
          <label className="field">
            <span>Gece Sayısı</span>
            <input name="nights" type="number" value={form.nights} onChange={onChange} />
          </label>
        </div>
        <div className="grid-2">
          <label className="field">
            <span>Fiyat (gecelik)</span>
            <input name="price_min" type="number" value={form.price_min} onChange={onChange} />
            <span className="field-help">
              Fiyatı net olarak girin (örn. 8000). Bu değer diğer otellere tek rakam olarak gösterilir.
            </span>
          </label>
        </div>
        <div className="grid-2">
          <label className="field">
            <span>Resim URL&apos;leri (virgülle ayır)</span>
            <textarea
              name="image_urls_raw"
              value={form.image_urls_raw}
              onChange={onChange}
              placeholder="https://...1.jpg, https://...2.jpg"
            />
            <span className="field-help">
              Oda/tesis görsellerinin linklerini virgülle ayırarak girin. Otel adı, logo, telefon, Instagram gibi kimlik bilgisi görünen görselleri kullanmayın.
            </span>
            <span className="field-help">
              ⚠️ Logo/tabela görünen görseller eşleşme sonrası gizlense bile talep düşürür.
            </span>
          </label>
          <label className="field">
            <span>Özellikler / İmkanlar (virgülle ayır)</span>
            <textarea
              name="features_raw"
              value={form.features_raw}
              onChange={onChange}
              placeholder="Şömine, Göl manzarası, Jakuzili"
            />
            <span className="field-help">
              Misafire değer katan özellikleri virgülle ayırarak girin. Örn: Şömine, Jakuzili, Göl manzarası, Özel bahçe, Kahvaltı dahil.
            </span>
            <div className="field-help">Hızlı ekle:</div>
            <div>
              {["Jakuzili","Şömine","Isıtmalı şömine / soba","Göl manzarası","Dağ manzarası","Özel bahçe","Havuz","Isıtmalı havuz","Kahvaltı dahil","Barbekü alanı","Evcil hayvan uygun","Otopark",].map((chip) => (
                <button
                  key={chip}
                  type="button"
                  className="feature-chip"
                  onClick={() => {
                    const current = form.features_raw
                      ? form.features_raw
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean)
                      : [];
                    if (!current.includes(chip)) {
                      const next = [...current, chip];
                      setForm({ ...form, features_raw: next.join(", ") });
                    }
                  }}
                >
                  {chip}
                </button>
              ))}
            </div>
          </label>
        </div>
        <button className="btn-primary" type="submit" data-testid="availability-submit">
          Kapasite Yayınla
        </button>
      </form>

      <h2 className="section-title">Aktif Kapasitelerim</h2>
      <div className="cards-grid">
        {mine.map((l) => (
          <div key={l.id} className="listing-card">
            {l.image_urls && l.image_urls.length > 0 && (
              <div className="listing-image-wrapper">
                <img src={l.image_urls[0]} alt="Kapasite görseli" className="listing-image" />
              </div>
            )}
            <div className="listing-header">
              <span className="badge-region">{l.region} / {l.micro_location}</span>
              <span className={`status-chip status-${l.availability_status}`}>
                {l.availability_status}
              </span>
            </div>
            <div className="listing-body">
              <div>Konsept: {l.concept}</div>
              <div>Kapasite: {l.capacity_label} ({l.pax} kişi)</div>
              {l.features && l.features.length > 0 && (
                <div className="listing-features">
                  {l.features.slice(0, 4).map((f) => (
                    <span key={f} className="feature-badge">
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Layout>
  );
};

const RequestsPage = () => {
  const [incoming, setIncoming] = React.useState([]);
  const [outgoing, setOutgoing] = React.useState([]);

  const load = async () => {
    const [inRes, outRes] = await Promise.all([
      axios.get("/requests/incoming"),
      axios.get("/requests/outgoing"),
    ]);
    setIncoming(inRes.data);
    setOutgoing(outRes.data);
  };

  React.useEffect(() => {
    load();
  }, []);

  const act = async (id, type) => {
    if (type === "accept") await axios.post(`/requests/${id}/accept`);
    if (type === "reject") await axios.post(`/requests/${id}/reject`);
    await load();
  };

  const statusLabel = (s) => {
    if (s === "pending") return "Beklemede";
    if (s === "accepted") return "Kabul";
    if (s === "rejected") return "Red";
    if (s === "alternative_offered") return "Alternatif Sunuldu";
    if (s === "cancelled") return "İptal";
    return s;
  };

  return (
    <Layout>
      <h1 className="page-title">B2B Talepler</h1>
      <div className="requests-grid">
        <section>
          <h2>Gelen Talepler</h2>
          <table className="requests-table" data-testid="incoming-table">
            <thead>
              <tr>
                <th>Listing</th>
                <th>Tip</th>
                <th>Süre</th>
                <th>Durum</th>
                <th>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {incoming.map((r) => (
                <tr key={r.id}>
                  <td>{r.listing_id.slice(0, 6)}...</td>
                  <td>{r.guest_type}</td>
                  <td>{r.confirm_window_minutes} dk</td>
                  <td>{statusLabel(r.status)}</td>
                  <td>
                    {r.status === "pending" && (
                      <>
                        <button
                          className="btn-sm btn-primary"
                          onClick={() => act(r.id, "accept")}
                          data-testid="incoming-accept"
                        >
                          Kabul
                        </button>
                        <button
                          className="btn-sm btn-ghost"
                          onClick={() => act(r.id, "reject")}
                          data-testid="incoming-reject"
                        >
                          Red
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section>
          <h2>Gönderilen Talepler</h2>
          <table className="requests-table" data-testid="outgoing-table">
            <thead>
              <tr>
                <th>Listing</th>
                <th>Tip</th>
                <th>Süre</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {outgoing.map((r) => (
                <tr key={r.id}>
                  <td>{r.listing_id.slice(0, 6)}...</td>
                  <td>{r.guest_type}</td>
                  <td>{r.confirm_window_minutes} dk</td>
                  <td>{statusLabel(r.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </Layout>
  );
};

const MatchesPage = () => {
  const [matches, setMatches] = React.useState([]);

  React.useEffect(() => {
    const load = async () => {
      const res = await axios.get("/matches");
      setMatches(res.data);
    };
    load();
  }, []);

  return (
    <Layout>
      <h1 className="page-title">Eşleşmeler</h1>
      <table className="requests-table" data-testid="matches-table">
        <thead>
          <tr>
            <th>Referans</th>
            <th>Kabul Tarihi</th>
            <th>Hizmet Bedeli</th>
            <th>Durum</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {matches.map((m) => (
            <tr key={m.id}>
              <td>{m.reference_code}</td>
              <td>{m.accepted_at ? new Date(m.accepted_at).toLocaleString() : "-"}</td>
              <td>{m.fee_amount} TL</td>
              <td>{m.fee_status}</td>
              <td>
                <Link to={`/matches/${m.id}`} data-testid="match-detail-link">
                  Detay
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Layout>
  );
};

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
      } catch (e) {
        setError("Bu eşleşme görüntülenemiyor veya yetkiniz yok.");
      }
    };
    load();
  }, [id]);

  const handleBack = () => {
    if (location.key !== "default") {
      navigate(-1);
    } else {
      navigate("/matches");
    }
  };

  if (error) {
    return (
      <Layout>
        <div className="overlay-modal">
          <div className="modal-panel">
            <div className="modal-header">
              <h1 className="page-title">Eşleşme Detayı</h1>
              <button className="btn-ghost" onClick={handleBack}>
                ×
              </button>
            </div>
            <div className="error" data-testid="match-error">{error}</div>
          </div>
        </div>
      </Layout>
    );
  }

  if (!data) {
    return (
      <Layout>
        <div className="overlay-modal">
          <div className="modal-panel">
            <div className="modal-header">
              <h1 className="page-title">Eşleşme Detayı</h1>
              <button className="btn-ghost" onClick={handleBack}>
                ×
              </button>
            </div>
            <div>Yükleniyor...</div>
          </div>
        </div>
      </Layout>
    );
  }

  const { reference_code, fee_amount, fee_status, accepted_at, counterparty } = data;
  const other = counterparty?.other || {};

  return (
    <Layout>
      <div className="overlay-modal">
        <div className="modal-panel">
          <div className="modal-header">
            <h1 className="page-title">Eşleşme Detayı</h1>
            <button className="btn-ghost" onClick={handleBack}>
              ×
            </button>
          </div>
          <div className="cards-row">
            <div className="kpi-card" data-testid="match-reference">
              <span>Referans Kodu</span>
              <strong>{reference_code}</strong>
            </div>
            <div className="kpi-card">
              <span>Kabul Tarihi</span>
              <strong>{accepted_at ? new Date(accepted_at).toLocaleString() : "-"}</strong>
            </div>
            <div className="kpi-card" data-testid="match-fee">
              <span>Bu Eşleşme İçin Hizmet Bedeli</span>
              <strong>{fee_amount} TL ({fee_status})</strong>
            </div>
          </div>

          <h2 className="section-title">Karşı Otel Bilgileri</h2>
          <div className="listing-card" data-testid="match-counterparty">
            <div className="listing-body">
              <div><strong>Ad:</strong> {other.name}</div>
              <div><strong>Bölge:</strong> {other.region} / {other.micro_location}</div>
              <div><strong>Konsept:</strong> {other.concept}</div>
              <div><strong>Adres:</strong> {other.address}</div>
              <div><strong>Telefon:</strong> {other.phone}</div>
              <div><strong>WhatsApp:</strong> {other.whatsapp}</div>
              <div><strong>Web Sitesi:</strong> {other.website}</div>
              <div><strong>İrtibat Kişisi:</strong> {other.contact_person}</div>
            </div>
          </div>

          <p className="section-note" data-testid="match-note">
            Bu eşleşme, otel → otel kapasite paylaşımı için oluşturulmuştur. Son kullanıcıya satış yapılmaz;
            platform yalnızca B2B eşleşme ve talep yönetimi sağlar.
          </p>
        </div>
      </div>
    </Layout>
  );
};

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

  React.useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await axios.get(`/listings/${id}`);
        setListing(res.data);
      } catch (e) {
        if (e.response && e.response.status === 404) {
          setError("Bu kapasite artık bulunmuyor.");
        } else {
          setError("Detay yüklenemedi.");
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const handleBack = () => {
    if (location.key !== "default") {
      navigate(-1);
    } else {
      navigate("/listings");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
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
      setSuccessMsg("Talep gönderildi. 120 dk içinde yanıt bekleniyor.");
    } catch (err) {
      setError("Talep gönderilirken hata oluştu.");
    } finally {
      setSubmitting(false);
    }
  };

  const isMobile = window.innerWidth < 768;

  const renderWrapper = (children) => (
    <Layout>
      {isMobile ? (
        <div className="detail-fullscreen">
          <header className="detail-header">
            <button className="btn-ghost" onClick={handleBack}>
              ←
            </button>
            <span>Anonim Kapasite</span>
          </header>
          <div className="detail-body">{children}</div>
        </div>
      ) : (
        <div className="overlay-modal">
          <div className="modal-panel">
            <div className="modal-header">
              <h1 className="page-title">Anonim Kapasite Detayı</h1>
              <button className="btn-ghost" onClick={handleBack}>
                ×
              </button>
            </div>
            <div className="modal-body">{children}</div>
          </div>
        </div>
      )}
    </Layout>
  );

  if (loading) {
    return renderWrapper(<div>Yükleniyor...</div>);
  }

  if (error) {
    return renderWrapper(
      <>
        <div className="error">{error}</div>
        <button className="btn-primary mt-2" onClick={handleBack}>
          Listeye dön
        </button>
      </>
    );
  }

  if (!listing) return null;

  const start = new Date(listing.date_start);
  const end = new Date(listing.date_end);

  const content = (
    <>
      <div className="detail-header-main">
        <div>
          <div className="detail-title-main">{listing.concept}</div>
          <div className="detail-subtitle">
            {listing.region} / {listing.micro_location}
          </div>
          <div className="detail-meta-row">
            <span>
              Tarih: {start.toLocaleDateString()} - {end.toLocaleDateString()} ({listing.nights} gece)
            </span>
            <span>
              Kapasite: {listing.capacity_label} / {listing.pax} pax
            </span>
          </div>
        </div>
      </div>

      <div className="detail-layout">
        <div className="detail-media">
          {listing.image_urls && listing.image_urls.length > 0 ? (
            <div className="detail-gallery">
              <div className="detail-gallery-main">
                <img src={listing.image_urls[0]} alt="Kapasite görseli" />
              </div>
              <div className="detail-gallery-thumbs">
                {listing.image_urls.slice(0, 4).map((url) => (
                  <img key={url} src={url} alt="Kapasite thumb" />
                ))}
                {listing.image_urls.length > 4 && (
                  <div className="detail-gallery-more">+{listing.image_urls.length - 4}</div>
                )}
              </div>
            </div>
          ) : (
            <div className="detail-gallery placeholder">Görsel eklenmedi</div>
          )}
        </div>

        <aside className="detail-meta-card">
          <div>
            <div className="detail-status">Durum: {listing.availability_status}</div>
            <div className="detail-price">
              Fiyat: {listing.price_min} TL / gece
            </div>
            {/* Referral rate indicator would go here if available in listing */}
          </div>
          {listing.is_locked && (
            <div className="detail-locked">Bu kapasite şu an kilitli. Bu kapasiteye başka bir talep açık.</div>
          )}
        </aside>
      </div>

      {listing.features && listing.features.length > 0 && (
        <section className="detail-section">
          <h2>Özellikler</h2>
          <div className="listing-features">
            {listing.features.map((f) => (
              <span key={f} className="feature-badge">
                {f}
              </span>
            ))}
          </div>
        </section>
      )}

      <section className="detail-section">
        <h2>Talep Bilgisi</h2>
        {successMsg && <div className="success mt-1">{successMsg}</div>}
        <form onSubmit={handleSubmit} className="detail-request-form">
          <label className="field">
            <span>Misafir Tipi</span>
            <select value={guestType} onChange={(e) => setGuestType(e.target.value)}>
              <option value="family">Aile</option>
              <option value="couple">Çift</option>
              <option value="group">Grup</option>
            </select>
          </label>
          <label className="field">
            <span>Not (opsiyonel)</span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Kısa not ekleyebilirsiniz"
            />
          </label>
          <div className="field-help">Onay süresi: 120 dk</div>
          <button
            className="btn-primary mt-2"
            type="submit"
            disabled={listing.is_locked || submitting}
          >
            {listing.is_locked ? "Şu an kilitli" : submitting ? "Gönderiliyor..." : "Talep Gönder"}
          </button>
        </form>
      </section>
    </>
  );

  if (isMobile) {
    return renderWrapper(
      <>
        {content}
        <div className="detail-sticky-cta">
          <button
            className="btn-primary w-full"
            onClick={handleSubmit}
            disabled={listing.is_locked || submitting}
          >
            {listing.is_locked ? "Şu an kilitli" : submitting ? "Gönderiliyor..." : "Talep Gönder"}
          </button>
        </div>
      </>
    );
  }

  return renderWrapper(content);
};

const App = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/listings"
            element={
              <ProtectedRoute>
                <ListingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/listings/:id"
            element={
              <ProtectedRoute>
                <ListingDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/availability"
            element={
              <ProtectedRoute>
                <AvailabilityPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/requests"
            element={
              <ProtectedRoute>
                <RequestsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/matches"
            element={
              <ProtectedRoute>
                <MatchesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/matches/:id"
            element={
              <ProtectedRoute>
                <MatchDetailPage />
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
