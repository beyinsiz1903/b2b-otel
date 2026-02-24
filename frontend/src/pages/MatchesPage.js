import React from "react";
import { Link } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";

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

export default MatchesPage;
