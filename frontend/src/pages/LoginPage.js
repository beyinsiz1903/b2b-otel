import React from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

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

export default LoginPage;
