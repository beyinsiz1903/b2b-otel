import React from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import axios from "@/utils/api";

const ResetPasswordPage = () => {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [done, setDone] = React.useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!token) { setError("Geçersiz veya eksik token. Lütfen yeni bir sıfırlama bağlantısı talep edin."); return; }
    if (newPassword !== confirm) { setError("Şifreler eşleşmiyor."); return; }
    setLoading(true);
    try {
      await axios.post("/auth/reset-password", { token, new_password: newPassword });
      setDone(true);
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Sıfırlama başarısız oldu. Bağlantı süresi dolmuş olabilir.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-panel">
        <div className="auth-logo">
          <div className="auth-logo-icon">🔐</div>
          <span style={{ fontWeight: 700, fontSize: "1.1rem", color: "#1a3a2a" }}>CapX</span>
        </div>
        <h1 className="auth-title">Yeni Şifre Belirle</h1>
        <p className="auth-subtitle">En az 8 karakter, büyük/küçük harf ve rakam içermelidir.</p>

        {done ? (
          <div className="success" style={{ background: "#e6f7ee", border: "1px solid #2da06b", color: "#1a3a2a", padding: "12px", borderRadius: "8px" }}>
            Şifreniz güncellendi. Giriş sayfasına yönlendiriliyorsunuz...
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form" data-testid="reset-form">
            <label className="field">
              <span>Yeni Şifre</span>
              <input
                data-testid="reset-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={8}
              />
            </label>
            <label className="field">
              <span>Yeni Şifre (Tekrar)</span>
              <input
                data-testid="reset-confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••"
                required
                minLength={8}
              />
            </label>
            {error && <div className="error" data-testid="reset-error">{error}</div>}
            <button data-testid="reset-submit" className="btn-primary w-full" type="submit" disabled={loading}>
              {loading ? <><span className="loading-spin" /> Güncelleniyor...</> : "Şifreyi Güncelle"}
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

export default ResetPasswordPage;
