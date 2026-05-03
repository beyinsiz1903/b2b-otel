import React from "react";
import { Link } from "react-router-dom";
import axios from "@/utils/api";

const ForgotPasswordPage = () => {
  const [email, setEmail] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [sent, setSent] = React.useState(false);
  const [error, setError] = React.useState("");
  const [debugToken, setDebugToken] = React.useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await axios.post("/auth/forgot-password", { email });
      setSent(true);
      if (res.data?.debug_token) setDebugToken(res.data.debug_token);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "İşlem başarısız oldu, lütfen tekrar deneyin.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-panel">
        <div className="auth-logo">
          <div className="auth-logo-icon">🔑</div>
          <span style={{ fontWeight: 700, fontSize: "1.1rem", color: "#1a3a2a" }}>CapX</span>
        </div>
        <h1 className="auth-title">Şifremi Unuttum</h1>
        <p className="auth-subtitle">
          Hesabınıza kayıtlı e-posta adresini girin; sıfırlama bağlantısını size göndereceğiz.
        </p>

        {sent ? (
          <div>
            <div className="success" style={{ background: "#e6f7ee", border: "1px solid #2da06b", color: "#1a3a2a", padding: "12px", borderRadius: "8px", marginBottom: "12px" }}>
              Eğer bu e-posta sistemde kayıtlıysa, sıfırlama bağlantısı 1 saat geçerli olmak üzere e-posta kutunuza gönderildi. Spam klasörünü de kontrol edin.
            </div>
            {debugToken && (
              <div style={{ background: "#fff8e1", padding: "10px", borderRadius: "6px", fontSize: "12px", marginBottom: "12px", wordBreak: "break-all" }}>
                <strong>DEV modu</strong> — token: <code>{debugToken}</code>
                <br />
                <Link to={`/reset-password?token=${debugToken}`}>Sıfırlama sayfasına git</Link>
              </div>
            )}
            <Link to="/login" className="btn-primary w-full" style={{ display: "block", textAlign: "center", textDecoration: "none" }}>
              Giriş sayfasına dön
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form" data-testid="forgot-form">
            <label className="field">
              <span>E-posta</span>
              <input
                data-testid="forgot-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="otel@example.com"
                required
              />
            </label>
            {error && <div className="error" data-testid="forgot-error">{error}</div>}
            <button data-testid="forgot-submit" className="btn-primary w-full" type="submit" disabled={loading}>
              {loading ? <><span className="loading-spin" /> Gönderiliyor...</> : "Sıfırlama Bağlantısı Gönder"}
            </button>
          </form>
        )}

        <div className="auth-links">
          <Link to="/login">← Giriş sayfasına dön</Link>
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
