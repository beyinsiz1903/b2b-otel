import React from "react";
import { useNavigate } from "react-router-dom";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";

const PerformancePage = () => {
  const { hotel } = useAuth();
  const [health, setHealth] = React.useState(null);
  const [benchmark, setBenchmark] = React.useState(null);
  const [indexes, setIndexes] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [benchLoading, setBenchLoading] = React.useState(false);
  const [tab, setTab] = React.useState("health");

  const loadHealth = async () => {
    try {
      const res = await axios.get("/performance/health");
      setHealth(res.data);
    } catch { }
    setLoading(false);
  };

  const runBenchmark = async () => {
    setBenchLoading(true);
    try {
      const res = await axios.get("/performance/benchmark");
      setBenchmark(res.data);
    } catch { }
    setBenchLoading(false);
  };

  const loadIndexes = async () => {
    try {
      const res = await axios.get("/performance/db-indexes");
      setIndexes(res.data);
    } catch { }
  };

  React.useEffect(() => { loadHealth(); }, []);

  if (!hotel?.is_admin) {
    return <Layout><div className="alert" style={{ background: "#fee2e2" }}>Bu sayfa sadece admin kullanıcılar içindir.</div></Layout>;
  }

  return (
    <Layout>
      <div className="page-header">
        <h1>🚀 Performans Merkezi</h1>
      </div>

      <div className="tab-bar" style={{ marginBottom: "1rem" }}>
        <button className={`tab-btn ${tab === "health" ? "active" : ""}`} onClick={() => setTab("health")}>💚 Sağlık</button>
        <button className={`tab-btn ${tab === "benchmark" ? "active" : ""}`} onClick={() => { setTab("benchmark"); if (!benchmark) runBenchmark(); }}>⚡ Benchmark</button>
        <button className={`tab-btn ${tab === "indexes" ? "active" : ""}`} onClick={() => { setTab("indexes"); if (!indexes) loadIndexes(); }}>🗂️ İndeksler</button>
      </div>

      {/* Sağlık Tab */}
      {tab === "health" && (
        <div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
            <button className="btn-primary btn-sm" onClick={loadHealth} disabled={loading}>🔄 Yenile</button>
          </div>

          {health && (
            <div>
              <div className="grid-3" style={{ marginBottom: "1rem" }}>
                <div className="card" style={{
                  padding: "1.25rem", textAlign: "center",
                  background: health.status === "healthy" ? "#f0fdf4" : "#fef3c7",
                  borderLeft: `4px solid ${health.status === "healthy" ? "#22c55e" : "#f59e0b"}`,
                }}>
                  <div style={{ fontSize: "2rem" }}>{health.status === "healthy" ? "✅" : "⚠️"}</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>{health.status === "healthy" ? "Sağlıklı" : "Dikkat"}</div>
                </div>
                <div className="card" style={{ padding: "1.25rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Toplam Yanıt</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{health.total_response_ms}ms</div>
                </div>
                <div className="card" style={{ padding: "1.25rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>MongoDB</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: health.checks?.mongodb?.status === "ok" ? "#16a34a" : "#dc2626" }}>
                    {health.checks?.mongodb?.latency_ms || "-"}ms
                  </div>
                </div>
              </div>

              {health.checks?.collections && (
                <div className="card" style={{ padding: "1.25rem" }}>
                  <h3 style={{ marginBottom: "0.75rem" }}>Koleksiyon Sayıları</h3>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>Koleksiyon</th><th>Kayıt Sayısı</th></tr></thead>
                      <tbody>
                        {Object.entries(health.checks.collections.counts).map(([name, count]) => (
                          <tr key={name}><td><strong>{name}</strong></td><td>{count}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "0.5rem" }}>
                    Sorgu süresi: {health.checks.collections.query_time_ms}ms
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Benchmark Tab */}
      {tab === "benchmark" && (
        <div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
            <button className="btn-primary btn-sm" onClick={runBenchmark} disabled={benchLoading}>
              {benchLoading ? "Test çalışıyor..." : "⚡ Benchmark Çalıştır"}
            </button>
          </div>

          {benchmark && (
            <div>
              <div className="grid-3" style={{ marginBottom: "1rem" }}>
                <div className="card" style={{
                  padding: "1.25rem", textAlign: "center",
                  background: benchmark.grade === "A" ? "#f0fdf4" : benchmark.grade === "B" ? "#eff6ff" : "#fef3c7",
                }}>
                  <div style={{ fontSize: "2.5rem", fontWeight: 700, color: benchmark.grade === "A" ? "#16a34a" : benchmark.grade === "B" ? "#2563eb" : "#f59e0b" }}>
                    {benchmark.grade}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "#64748b" }}>{benchmark.grade_description}</div>
                </div>
                <div className="card" style={{ padding: "1.25rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Toplam Süre</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{benchmark.total_ms}ms</div>
                </div>
                <div className="card" style={{ padding: "1.25rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Test Sayısı</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{Object.keys(benchmark.benchmarks).length}</div>
                </div>
              </div>

              <div className="card" style={{ padding: "1.25rem" }}>
                <h3 style={{ marginBottom: "0.75rem" }}>Test Detayları</h3>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Test</th><th>Süre (ms)</th><th>Durum</th></tr></thead>
                    <tbody>
                      {Object.entries(benchmark.benchmarks).map(([name, data]) => (
                        <tr key={name}>
                          <td><strong>{name.replace(/_/g, " ")}</strong></td>
                          <td>{data.time_ms}ms</td>
                          <td>
                            <span style={{
                              padding: "0.15rem 0.5rem", borderRadius: "999px", fontSize: "0.75rem",
                              background: data.time_ms < 10 ? "#dcfce7" : data.time_ms < 50 ? "#eff6ff" : "#fef3c7",
                              color: data.time_ms < 10 ? "#166534" : data.time_ms < 50 ? "#1e40af" : "#92400e",
                            }}>
                              {data.time_ms < 10 ? "Hızlı" : data.time_ms < 50 ? "Normal" : "Yavaş"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Visual Bar Chart */}
              <div className="card" style={{ padding: "1.25rem", marginTop: "1rem" }}>
                <h3 style={{ marginBottom: "0.75rem" }}>Performans Grafiği</h3>
                {Object.entries(benchmark.benchmarks).map(([name, data]) => {
                  const maxMs = Math.max(...Object.values(benchmark.benchmarks).map(d => d.time_ms));
                  const pct = maxMs > 0 ? Math.max((data.time_ms / maxMs) * 100, 2) : 2;
                  return (
                    <div key={name} style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
                      <div style={{ width: "140px", fontSize: "0.75rem", textAlign: "right", color: "#64748b" }}>{name.replace(/_/g, " ")}</div>
                      <div style={{ flex: 1, height: "20px", background: "#f1f5f9", borderRadius: "4px", overflow: "hidden" }}>
                        <div style={{
                          width: `${pct}%`, height: "100%",
                          background: data.time_ms < 10 ? "#22c55e" : data.time_ms < 50 ? "#3b82f6" : "#f59e0b",
                          borderRadius: "4px",
                          transition: "width 0.5s ease",
                        }} />
                      </div>
                      <div style={{ width: "60px", fontSize: "0.75rem", fontWeight: 600 }}>{data.time_ms}ms</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* İndeksler Tab */}
      {tab === "indexes" && (
        <div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
            <button className="btn-primary btn-sm" onClick={loadIndexes}>🔄 Yenile</button>
          </div>

          {indexes && (
            <div className="card" style={{ padding: "1.25rem" }}>
              <h3 style={{ marginBottom: "0.75rem" }}>MongoDB İndeksleri</h3>
              {Object.entries(indexes).map(([coll, idxs]) => (
                <div key={coll} style={{ marginBottom: "1rem" }}>
                  <h4 style={{ fontSize: "0.9rem", color: "#1e40af", marginBottom: "0.25rem" }}>📁 {coll}</h4>
                  {idxs.error ? (
                    <div style={{ color: "#dc2626", fontSize: "0.8rem" }}>Hata: {idxs.error}</div>
                  ) : (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
                      {Object.entries(idxs).map(([idxName, info]) => (
                        <span key={idxName} className="chip" style={{ fontSize: "0.7rem" }}>
                          {idxName}: {info.keys?.map(k => k.join(":")).join(", ")}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Layout>
  );
};


export default PerformancePage;
