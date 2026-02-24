import React from "react";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";

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


export default SubscriptionPage;
