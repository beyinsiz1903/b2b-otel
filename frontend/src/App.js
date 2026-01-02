import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
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
          <a href="/dashboard" data-testid="nav-dashboard">Panel</a>
          <a href="/listings" data-testid="nav-listings">Anonim Kapasiteler</a>
          <a href="/availability" data-testid="nav-availability">Kendi Kapasitem</a>
          <a href="/requests" data-testid="nav-requests">Talepler</a>
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
        setStats({
          outgoing: outRes.data.length,
          incoming: inRes.data.length,
          matches: matchesRes.data.length,
        });
      } catch {
        setStats({ outgoing: 0, incoming: 0, matches: 0 });
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
      </div>
    </Layout>
  );
};

const ListingsPage = () => {
  const [listings, setListings] = React.useState([]);

  const load = async () => {
    const res = await axios.get("/listings");
    setListings(res.data);
  };

  React.useEffect(() => {
    load();
  }, []);

  const sendRequest = async (listingId) => {
    await axios.post("/requests", {
      listing_id: listingId,
      guest_type: "family",
      notes: "",
      confirm_window_minutes: 120,
    });
    await load();
  };

  return (
    <Layout>
      <h1 className="page-title">Anonim Kapasite Listesi</h1>
      <div className="cards-grid">
        {listings.map((l) => (
          <div className="listing-card" key={l.id} data-testid="listing-card">
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
              <div>Fiyat Aralığı: {l.price_min} - {l.price_max} TL</div>
            </div>
            <button
              className="btn-primary w-full mt-2"
              onClick={() => sendRequest(l.id)}
              disabled={l.is_locked}
              data-testid="send-request-button"
            >
              {l.is_locked ? "Bu kapasite şu an kilitli" : "Talep Gönder"}
            </button>
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
    await axios.post("/listings", {
      ...form,
      pax: Number(form.pax),
      nights: Number(form.nights),
      price_min: Number(form.price_min),
      price_max: Number(form.price_max),
      date_start: new Date(form.date_start).toISOString(),
      date_end: new Date(form.date_end).toISOString(),
    });
    await loadMine();
  };

  return (
    <Layout>
      <h1 className="page-title">Kendi Kapasitelerim</h1>
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
          </label>
          <label className="field">
            <span>Gece Sayısı</span>
            <input name="nights" type="number" value={form.nights} onChange={onChange} />
          </label>
        </div>
        <div className="grid-2">
          <label className="field">
            <span>Fiyat Min</span>
            <input name="price_min" type="number" value={form.price_min} onChange={onChange} />
          </label>
          <label className="field">
            <span>Fiyat Max</span>
            <input name="price_max" type="number" value={form.price_max} onChange={onChange} />
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
            <div className="listing-header">
              <span className="badge-region">{l.region} / {l.micro_location}</span>
              <span className={`status-chip status-${l.availability_status}`}>
                {l.availability_status}
              </span>
            </div>
            <div className="listing-body">
              <div>Konsept: {l.concept}</div>
              <div>Kapasite: {l.capacity_label} ({l.pax} kişi)</div>
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
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
