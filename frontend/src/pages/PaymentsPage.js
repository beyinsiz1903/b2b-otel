import React from "react";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Modal from "@/components/Modal";

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


export default PaymentsPage;
