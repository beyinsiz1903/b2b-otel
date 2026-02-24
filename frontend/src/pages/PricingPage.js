import React from "react";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Modal from "@/components/Modal";
import { ROOM_TYPES_INV, RULE_TYPES } from "@/utils/constants";

// ── Pricing Engine Page ──────────────────────────────────────────────────────

// ── Pricing Engine Page ──────────────────────────────────────────────────────

const PricingPage = () => {
  const [rules, setRules] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [showCreate, setShowCreate] = React.useState(false);
  const [editRule, setEditRule] = React.useState(null);
  const [deleteConfirm, setDeleteConfirm] = React.useState(null);
  const [msg, setMsg] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [tab, setTab] = React.useState("rules");

  // Calculator state
  const [calcForm, setCalcForm] = React.useState({
    room_type: "standart", date_start: "", date_end: "", base_price: "",
  });
  const [calcResult, setCalcResult] = React.useState(null);
  const [calcLoading, setCalcLoading] = React.useState(false);

  // Market comparison state
  const [marketData, setMarketData] = React.useState(null);
  const [marketRoom, setMarketRoom] = React.useState("");
  const [marketRegion, setMarketRegion] = React.useState("");
  const [marketLoading, setMarketLoading] = React.useState(false);

  // Price history
  const [historyData, setHistoryData] = React.useState(null);
  const [historyLoading, setHistoryLoading] = React.useState(false);

  const defaultRule = {
    name: "", rule_type: "seasonal", room_type: "", multiplier: 1.0,
    date_start: "", date_end: "", occupancy_threshold_min: "", occupancy_threshold_max: "",
    days_before_min: "", days_before_max: "", weekend_days: [5, 6],
    is_active: true, priority: 0,
  };
  const [ruleForm, setRuleForm] = React.useState(defaultRule);

  const loadRules = async () => {
    try {
      const res = await axios.get("/pricing/rules");
      setRules(res.data);
    } catch { }
    setLoading(false);
  };

  React.useEffect(() => { loadRules(); }, []);

  const handleCreateRule = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    try {
      const payload = {
        name: ruleForm.name,
        rule_type: ruleForm.rule_type,
        multiplier: parseFloat(ruleForm.multiplier),
        room_type: ruleForm.room_type || null,
        is_active: ruleForm.is_active,
        priority: parseInt(ruleForm.priority) || 0,
      };
      if (ruleForm.rule_type === "seasonal" || ruleForm.rule_type === "holiday") {
        payload.date_start = ruleForm.date_start || null;
        payload.date_end = ruleForm.date_end || null;
      }
      if (ruleForm.rule_type === "occupancy") {
        payload.occupancy_threshold_min = ruleForm.occupancy_threshold_min ? parseFloat(ruleForm.occupancy_threshold_min) : null;
        payload.occupancy_threshold_max = ruleForm.occupancy_threshold_max ? parseFloat(ruleForm.occupancy_threshold_max) : null;
      }
      if (ruleForm.rule_type === "early_bird" || ruleForm.rule_type === "last_minute") {
        payload.days_before_min = ruleForm.days_before_min ? parseInt(ruleForm.days_before_min) : null;
        payload.days_before_max = ruleForm.days_before_max ? parseInt(ruleForm.days_before_max) : null;
      }
      if (ruleForm.rule_type === "weekend") {
        payload.weekend_days = ruleForm.weekend_days;
      }

      if (editRule) {
        await axios.put(`/pricing/rules/${editRule.id}`, payload);
        setMsg("Kural güncellendi!");
      } else {
        await axios.post("/pricing/rules", payload);
        setMsg("Kural oluşturuldu!");
      }
      setShowCreate(false);
      setEditRule(null);
      setRuleForm(defaultRule);
      loadRules();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hata oluştu");
    }
    setSaving(false);
  };

  const handleDeleteRule = async () => {
    if (!deleteConfirm) return;
    try {
      await axios.delete(`/pricing/rules/${deleteConfirm.id}`);
      setDeleteConfirm(null);
      loadRules();
    } catch { }
  };

  const handleCalculate = async (e) => {
    e.preventDefault();
    setCalcLoading(true);
    setCalcResult(null);
    try {
      const res = await axios.post("/pricing/calculate", {
        room_type: calcForm.room_type,
        date_start: calcForm.date_start,
        date_end: calcForm.date_end,
        base_price: parseFloat(calcForm.base_price),
      });
      setCalcResult(res.data);
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hesaplama hatası");
    }
    setCalcLoading(false);
  };

  const loadMarket = async () => {
    setMarketLoading(true);
    try {
      const params = {};
      if (marketRoom) params.room_type = marketRoom;
      if (marketRegion) params.region = marketRegion;
      const res = await axios.get("/pricing/market-comparison", { params });
      setMarketData(res.data);
    } catch { }
    setMarketLoading(false);
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await axios.get("/pricing/history", { params: { months: 6 } });
      setHistoryData(res.data);
    } catch { }
    setHistoryLoading(false);
  };

  const startEditRule = (rule) => {
    setEditRule(rule);
    setRuleForm({
      name: rule.name,
      rule_type: rule.rule_type,
      room_type: rule.room_type || "",
      multiplier: rule.multiplier,
      date_start: rule.date_start || "",
      date_end: rule.date_end || "",
      occupancy_threshold_min: rule.occupancy_threshold_min ?? "",
      occupancy_threshold_max: rule.occupancy_threshold_max ?? "",
      days_before_min: rule.days_before_min ?? "",
      days_before_max: rule.days_before_max ?? "",
      weekend_days: rule.weekend_days || [5, 6],
      is_active: rule.is_active,
      priority: rule.priority,
    });
    setShowCreate(true);
  };

  const multiplierLabel = (m) => {
    if (m > 1) return `+${Math.round((m - 1) * 100)}%`;
    if (m < 1) return `-${Math.round((1 - m) * 100)}%`;
    return "Değişiklik yok";
  };

  return (
    <Layout>
      <div className="page-header">
        <h1>💰 Fiyatlama Motoru</h1>
      </div>

      {msg && <div className="alert" style={{ marginBottom: "1rem" }}>{msg}</div>}

      {/* Tabs */}
      <div className="tab-bar" style={{ marginBottom: "1rem" }}>
        <button className={`tab-btn ${tab === "rules" ? "active" : ""}`} onClick={() => setTab("rules")}>📋 Kurallar</button>
        <button className={`tab-btn ${tab === "calculator" ? "active" : ""}`} onClick={() => setTab("calculator")}>🧮 Hesaplayıcı</button>
        <button className={`tab-btn ${tab === "market" ? "active" : ""}`} onClick={() => { setTab("market"); if (!marketData) loadMarket(); }}>📊 Piyasa</button>
        <button className={`tab-btn ${tab === "history" ? "active" : ""}`} onClick={() => { setTab("history"); if (!historyData) loadHistory(); }}>📈 Geçmiş</button>
      </div>

      {/* Kurallar Tab */}
      {tab === "rules" && (
        <div className="card" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h3>Fiyatlama Kuralları ({rules.length})</h3>
            <button className="btn-primary btn-sm" onClick={() => { setEditRule(null); setRuleForm(defaultRule); setShowCreate(true); }}>+ Yeni Kural</button>
          </div>

          {rules.length === 0 ? (
            <div style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>
              Henüz fiyatlama kuralı yok. Sezon, hafta sonu veya doluluk bazlı kurallar ekleyebilirsiniz.
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Kural Adı</th>
                    <th>Tip</th>
                    <th>Çarpan</th>
                    <th>Oda Tipi</th>
                    <th>Durum</th>
                    <th>Öncelik</th>
                    <th>İşlem</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => {
                    const rt = RULE_TYPES.find(r => r.value === rule.rule_type);
                    return (
                      <tr key={rule.id}>
                        <td><strong>{rule.name}</strong></td>
                        <td>{rt ? `${rt.icon} ${rt.label}` : rule.rule_type}</td>
                        <td>
                          <span style={{
                            color: rule.multiplier > 1 ? "#dc2626" : rule.multiplier < 1 ? "#16a34a" : "#64748b",
                            fontWeight: 600,
                          }}>
                            x{rule.multiplier} ({multiplierLabel(rule.multiplier)})
                          </span>
                        </td>
                        <td>{rule.room_type || "Tümü"}</td>
                        <td>
                          <span className={`chip ${rule.is_active ? "chip-green" : "chip-gray"}`}>
                            {rule.is_active ? "Aktif" : "Pasif"}
                          </span>
                        </td>
                        <td>{rule.priority}</td>
                        <td>
                          <div style={{ display: "flex", gap: "0.3rem" }}>
                            <button className="btn-secondary btn-sm" onClick={() => startEditRule(rule)}>✏️</button>
                            <button className="btn-danger btn-sm" onClick={() => setDeleteConfirm(rule)}>🗑️</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Hesaplayıcı Tab */}
      {tab === "calculator" && (
        <div className="card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "1rem" }}>🧮 Dinamik Fiyat Hesaplayıcı</h3>
          <form onSubmit={handleCalculate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <div>
              <label className="field-label">Oda Tipi</label>
              <select className="field" value={calcForm.room_type} onChange={(e) => setCalcForm({ ...calcForm, room_type: e.target.value })}>
                {ROOM_TYPES_INV.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label">Baz Fiyat (₺/gece)</label>
              <input className="field" type="number" min={0} step="0.01" value={calcForm.base_price}
                onChange={(e) => setCalcForm({ ...calcForm, base_price: e.target.value })} required />
            </div>
            <div>
              <label className="field-label">Başlangıç</label>
              <input className="field" type="date" value={calcForm.date_start}
                onChange={(e) => setCalcForm({ ...calcForm, date_start: e.target.value })} required />
            </div>
            <div>
              <label className="field-label">Bitiş</label>
              <input className="field" type="date" value={calcForm.date_end}
                onChange={(e) => setCalcForm({ ...calcForm, date_end: e.target.value })} required />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <button type="submit" className="btn-primary" disabled={calcLoading}>{calcLoading ? "Hesaplanıyor..." : "Hesapla"}</button>
            </div>
          </form>

          {calcResult && (
            <div style={{ marginTop: "1.25rem" }}>
              <div className="grid-3" style={{ marginBottom: "1rem" }}>
                <div className="card" style={{ padding: "1rem", textAlign: "center", background: "#f0fdf4" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Toplam Fiyat</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#166534" }}>{calcResult.total_price}₺</div>
                </div>
                <div className="card" style={{ padding: "1rem", textAlign: "center", background: "#eff6ff" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Ort. Gece</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#1e40af" }}>{calcResult.average_price}₺</div>
                </div>
                <div className="card" style={{ padding: "1rem", textAlign: "center", background: "#faf5ff" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Gece Sayısı</div>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#7c3aed" }}>{calcResult.night_count}</div>
                </div>
              </div>

              <h4 style={{ marginBottom: "0.5rem" }}>Günlük Dağılım</h4>
              <div className="table-wrap" style={{ maxHeight: "300px", overflowY: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Tarih</th>
                      <th>Baz Fiyat</th>
                      <th>Son Fiyat</th>
                      <th>Çarpan</th>
                      <th>Uygulanan Kurallar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calcResult.daily_breakdown.map((d) => (
                      <tr key={d.date}>
                        <td>{d.date}</td>
                        <td>{d.base_price}₺</td>
                        <td style={{ fontWeight: 600, color: d.final_price > d.base_price ? "#dc2626" : d.final_price < d.base_price ? "#16a34a" : "#1e293b" }}>
                          {d.final_price}₺
                        </td>
                        <td>x{d.final_multiplier}</td>
                        <td>
                          {d.applied_rules.length === 0 ? <span style={{ color: "#94a3b8" }}>-</span> :
                            d.applied_rules.map(r => <span key={r.rule_id} className="chip" style={{ marginRight: "0.25rem" }}>{r.name}</span>)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Piyasa Tab */}
      {tab === "market" && (
        <div className="card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "1rem" }}>📊 Piyasa Karşılaştırması</h3>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            <select className="field" style={{ width: "auto" }} value={marketRoom} onChange={(e) => setMarketRoom(e.target.value)}>
              <option value="">Tüm Oda Tipleri</option>
              {ROOM_TYPES_INV.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
            <select className="field" style={{ width: "auto" }} value={marketRegion} onChange={(e) => setMarketRegion(e.target.value)}>
              <option value="">Tüm Bölgeler</option>
              <option value="Sapanca">Sapanca</option>
              <option value="Kartepe">Kartepe</option>
              <option value="Abant">Abant</option>
              <option value="Ayder">Ayder</option>
              <option value="Kas">Kaş</option>
              <option value="Alacati">Alaçatı</option>
              <option value="Maşukiye">Maşukiye</option>
            </select>
            <button className="btn-primary btn-sm" onClick={loadMarket} disabled={marketLoading}>
              {marketLoading ? "Yükleniyor..." : "Karşılaştır"}
            </button>
          </div>

          {marketData && (
            <div>
              <div className="grid-3" style={{ marginBottom: "1rem" }}>
                <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Piyasa Ort. (min)</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700 }}>{marketData.avg_price_min ? `${marketData.avg_price_min}₺` : "-"}</div>
                </div>
                <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>Sizin Ort.</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#7c3aed" }}>{marketData.my_avg_price ? `${marketData.my_avg_price}₺` : "-"}</div>
                </div>
                <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>İlan Sayısı</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700 }}>{marketData.sample_size}</div>
                </div>
              </div>

              {marketData.min_price && marketData.max_price && (
                <div style={{ background: "#f8fafc", padding: "1rem", borderRadius: "0.5rem", marginBottom: "1rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                    <span>Min: {marketData.min_price}₺</span>
                    <span>Medyan: {marketData.median_price}₺</span>
                    <span>Max: {marketData.max_price}₺</span>
                  </div>
                  <div style={{ width: "100%", height: "8px", background: "#e2e8f0", borderRadius: "4px", position: "relative" }}>
                    {marketData.my_avg_price && (
                      <div style={{
                        position: "absolute",
                        left: `${Math.min(((marketData.my_avg_price - marketData.min_price) / (marketData.max_price - marketData.min_price)) * 100, 100)}%`,
                        top: "-4px",
                        width: "16px", height: "16px",
                        background: "#7c3aed", borderRadius: "50%", border: "2px solid #fff",
                        transform: "translateX(-50%)",
                      }} title={`Sizin fiyatınız: ${marketData.my_avg_price}₺`} />
                    )}
                  </div>
                </div>
              )}

              <div className="alert" style={{
                background: marketData.recommendation.includes("indirim") ? "#fef3c7" :
                  marketData.recommendation.includes("artış") ? "#dcfce7" : "#eff6ff",
                borderLeft: "4px solid",
                borderLeftColor: marketData.recommendation.includes("indirim") ? "#f59e0b" :
                  marketData.recommendation.includes("artış") ? "#22c55e" : "#3b82f6",
              }}>
                💡 <strong>Öneri:</strong> {marketData.recommendation}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Geçmiş Tab */}
      {tab === "history" && (
        <div className="card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "1rem" }}>📈 Fiyat Geçmişi (Son 6 Ay)</h3>
          {historyLoading ? <div>Yükleniyor...</div> : historyData && historyData.history.length > 0 ? (
            <div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Ay</th>
                      <th>Ort. Min Fiyat</th>
                      <th>Ort. Max Fiyat</th>
                      <th>İlan Sayısı</th>
                      <th>En Düşük</th>
                      <th>En Yüksek</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyData.history.map((h) => (
                      <tr key={h.month}>
                        <td><strong>{h.month}</strong></td>
                        <td>{h.avg_price_min}₺</td>
                        <td>{h.avg_price_max}₺</td>
                        <td>{h.listing_count}</td>
                        <td style={{ color: "#16a34a" }}>{h.min_price}₺</td>
                        <td style={{ color: "#dc2626" }}>{h.max_price}₺</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Simple bar chart */}
              <div style={{ marginTop: "1.25rem" }}>
                <h4 style={{ marginBottom: "0.5rem" }}>Fiyat Trendi</h4>
                <div style={{ display: "flex", alignItems: "flex-end", gap: "0.5rem", height: "150px" }}>
                  {historyData.history.map((h) => {
                    const maxPrice = Math.max(...historyData.history.map(x => x.avg_price_max));
                    const pct = maxPrice > 0 ? Math.max((h.avg_price_max / maxPrice) * 100, 5) : 5;
                    return (
                      <div key={h.month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <div style={{ fontSize: "0.7rem", marginBottom: "0.25rem" }}>{h.avg_price_max}₺</div>
                        <div style={{
                          width: "100%", height: `${pct}%`,
                          background: "linear-gradient(to top, #7c3aed, #a78bfa)",
                          borderRadius: "4px 4px 0 0",
                          minHeight: "4px",
                        }} />
                        <div style={{ fontSize: "0.65rem", marginTop: "0.25rem", color: "#64748b" }}>{h.month.split("-")[1]}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>Henüz fiyat geçmişi yok.</div>
          )}
        </div>
      )}

      {/* Kural Oluştur/Düzenle Modal */}
      <Modal open={showCreate} onClose={() => { setShowCreate(false); setEditRule(null); }} title={editRule ? "Kuralı Düzenle" : "Yeni Fiyatlama Kuralı"} size="lg">
        <form onSubmit={handleCreateRule}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <div>
              <label className="field-label">Kural Adı</label>
              <input className="field" value={ruleForm.name} onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })} placeholder="Yaz Sezonu %30" required />
            </div>
            <div>
              <label className="field-label">Kural Tipi</label>
              <select className="field" value={ruleForm.rule_type} onChange={(e) => setRuleForm({ ...ruleForm, rule_type: e.target.value })}>
                {RULE_TYPES.map(r => <option key={r.value} value={r.value}>{r.icon} {r.label}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label">Fiyat Çarpanı (1.0 = değişiklik yok)</label>
              <input className="field" type="number" step="0.01" min="0.1" max="5" value={ruleForm.multiplier}
                onChange={(e) => setRuleForm({ ...ruleForm, multiplier: e.target.value })} required />
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.25rem" }}>
                {ruleForm.multiplier > 1 ? `${Math.round((ruleForm.multiplier - 1) * 100)}% artış` :
                  ruleForm.multiplier < 1 ? `${Math.round((1 - ruleForm.multiplier) * 100)}% indirim` : "Değişiklik yok"}
              </div>
            </div>
            <div>
              <label className="field-label">Oda Tipi (boş = tümü)</label>
              <select className="field" value={ruleForm.room_type} onChange={(e) => setRuleForm({ ...ruleForm, room_type: e.target.value })}>
                <option value="">Tüm Oda Tipleri</option>
                {ROOM_TYPES_INV.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>

            {/* Conditional fields based on rule_type */}
            {(ruleForm.rule_type === "seasonal" || ruleForm.rule_type === "holiday") && (
              <>
                <div>
                  <label className="field-label">Başlangıç Tarihi</label>
                  <input className="field" type="date" value={ruleForm.date_start} onChange={(e) => setRuleForm({ ...ruleForm, date_start: e.target.value })} />
                </div>
                <div>
                  <label className="field-label">Bitiş Tarihi</label>
                  <input className="field" type="date" value={ruleForm.date_end} onChange={(e) => setRuleForm({ ...ruleForm, date_end: e.target.value })} />
                </div>
              </>
            )}

            {ruleForm.rule_type === "occupancy" && (
              <>
                <div>
                  <label className="field-label">Min Doluluk Oranı (0-1)</label>
                  <input className="field" type="number" step="0.1" min="0" max="1" value={ruleForm.occupancy_threshold_min}
                    onChange={(e) => setRuleForm({ ...ruleForm, occupancy_threshold_min: e.target.value })} placeholder="0.7" />
                </div>
                <div>
                  <label className="field-label">Max Doluluk Oranı (0-1)</label>
                  <input className="field" type="number" step="0.1" min="0" max="1" value={ruleForm.occupancy_threshold_max}
                    onChange={(e) => setRuleForm({ ...ruleForm, occupancy_threshold_max: e.target.value })} placeholder="1.0" />
                </div>
              </>
            )}

            {(ruleForm.rule_type === "early_bird" || ruleForm.rule_type === "last_minute") && (
              <>
                <div>
                  <label className="field-label">Min Gün Öncesi</label>
                  <input className="field" type="number" min="0" value={ruleForm.days_before_min}
                    onChange={(e) => setRuleForm({ ...ruleForm, days_before_min: e.target.value })} placeholder={ruleForm.rule_type === "early_bird" ? "30" : "0"} />
                </div>
                <div>
                  <label className="field-label">Max Gün Öncesi</label>
                  <input className="field" type="number" min="0" value={ruleForm.days_before_max}
                    onChange={(e) => setRuleForm({ ...ruleForm, days_before_max: e.target.value })} placeholder={ruleForm.rule_type === "early_bird" ? "365" : "7"} />
                </div>
              </>
            )}

            {ruleForm.rule_type === "weekend" && (
              <div style={{ gridColumn: "1 / -1" }}>
                <label className="field-label">Hafta Sonu Günleri</label>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((day, idx) => (
                    <label key={idx} style={{ display: "flex", alignItems: "center", gap: "0.25rem", cursor: "pointer" }}>
                      <input type="checkbox" checked={ruleForm.weekend_days.includes(idx)}
                        onChange={() => {
                          const days = ruleForm.weekend_days.includes(idx)
                            ? ruleForm.weekend_days.filter(d => d !== idx)
                            : [...ruleForm.weekend_days, idx];
                          setRuleForm({ ...ruleForm, weekend_days: days });
                        }} />
                      {day}
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div>
              <label className="field-label">Öncelik (yüksek = önce uygulanır)</label>
              <input className="field" type="number" value={ruleForm.priority}
                onChange={(e) => setRuleForm({ ...ruleForm, priority: e.target.value })} />
            </div>
            <div style={{ display: "flex", alignItems: "end" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                <input type="checkbox" checked={ruleForm.is_active}
                  onChange={(e) => setRuleForm({ ...ruleForm, is_active: e.target.checked })} />
                Aktif
              </label>
            </div>
          </div>

          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => { setShowCreate(false); setEditRule(null); }}>İptal</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Kaydediliyor..." : editRule ? "Güncelle" : "Oluştur"}</button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!deleteConfirm}
        title="Kuralı Sil"
        message={`"${deleteConfirm?.name}" fiyatlama kuralını silmek istediğinize emin misiniz?`}
        onConfirm={handleDeleteRule}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Layout>
  );
};

export default PricingPage;
