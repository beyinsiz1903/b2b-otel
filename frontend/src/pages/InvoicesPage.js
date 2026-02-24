import React from "react";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Modal from "@/components/Modal";

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
                    <td><button className="btn-ghost btn-sm" onClick={() => setDetail(inv)}>Detay</button>
                    <button className="btn-ghost btn-sm" style={{ marginLeft: "0.25rem" }} onClick={async () => {
                      try {
                        const res = await axios.get(`/invoices/${inv.id}/pdf`, { responseType: "blob" });
                        const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `fatura-${inv.invoice_number}.pdf`;
                        a.click();
                        window.URL.revokeObjectURL(url);
                      } catch { alert("PDF indirilemedi"); }
                    }}>📄 PDF</button></td>
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


export default InvoicesPage;
