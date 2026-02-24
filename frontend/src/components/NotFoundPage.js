import React from "react";
import { Link } from "react-router-dom";

const NotFoundPage = () => (
  <div className="error-boundary-page">
    <div className="error-boundary-card">
      <div style={{ fontSize: "4rem", marginBottom: "1rem" }}>🔍</div>
      <h1 style={{ fontSize: "3rem", color: "#2e6b57", marginBottom: "0.5rem" }}>404</h1>
      <h2 style={{ marginBottom: "0.5rem" }}>Sayfa Bulunamadı</h2>
      <p>Aradığınız sayfa mevcut değil veya taşınmış olabilir.</p>
      <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem" }}>
        <Link to="/dashboard" className="btn-primary" style={{ textDecoration: "none" }}>Ana Sayfa</Link>
        <button className="btn-ghost" onClick={() => window.history.back()}>Geri Dön</button>
      </div>
    </div>
  </div>
);

export default NotFoundPage;
