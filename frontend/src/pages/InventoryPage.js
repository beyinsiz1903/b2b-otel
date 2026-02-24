import React from "react";
import axios from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Modal from "@/components/Modal";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ROOM_TYPES_INV } from "@/utils/constants";

// ── Inventory Management Page ─────────────────────────────────────────────────

const InventoryPage = () => {
  const [items, setItems] = React.useState([]);
  const [summary, setSummary] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [showCreate, setShowCreate] = React.useState(false);
  const [editItem, setEditItem] = React.useState(null);
  const [calendarItem, setCalendarItem] = React.useState(null);
  const [calendarData, setCalendarData] = React.useState(null);
  const [calendarMonth, setCalendarMonth] = React.useState(() => {
    const n = new Date();
    return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}`;
  });
  const [bulkModal, setBulkModal] = React.useState(null);
  const [deleteConfirm, setDeleteConfirm] = React.useState(null);

  const [form, setForm] = React.useState({
    room_type: "standart", room_type_name: "", total_rooms: 1,
    description: "", capacity_label: "", pax: 2,
  });
  const [bulkForm, setBulkForm] = React.useState({
    date_start: "", date_end: "", available_rooms: 0, price_per_night: "",
  });
  const [saving, setSaving] = React.useState(false);
  const [msg, setMsg] = React.useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [itemsRes, summaryRes] = await Promise.all([
        axios.get("/inventory"),
        axios.get("/inventory/summary/all"),
      ]);
      setItems(itemsRes.data);
      setSummary(summaryRes.data);
    } catch { }
    setLoading(false);
  };

  React.useEffect(() => { load(); }, []);

  const loadCalendar = async (invId, month) => {
    try {
      const res = await axios.get(`/inventory/${invId}/calendar`, { params: { month } });
      setCalendarData(res.data);
    } catch { }
  };

  React.useEffect(() => {
    if (calendarItem) loadCalendar(calendarItem._id || calendarItem.id, calendarMonth);
  }, [calendarItem, calendarMonth]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    try {
      await axios.post("/inventory", {
        room_type: form.room_type,
        room_type_name: form.room_type_name,
        total_rooms: parseInt(form.total_rooms),
        description: form.description || null,
        capacity_label: form.capacity_label || null,
        pax: parseInt(form.pax) || null,
      });
      setMsg("Envanter kalemi oluşturuldu!");
      setShowCreate(false);
      setForm({ room_type: "standart", room_type_name: "", total_rooms: 1, description: "", capacity_label: "", pax: 2 });
      load();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hata oluştu");
    }
    setSaving(false);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!editItem) return;
    setSaving(true);
    try {
      await axios.put(`/inventory/${editItem.id}`, {
        room_type_name: form.room_type_name || undefined,
        total_rooms: parseInt(form.total_rooms) || undefined,
        description: form.description || undefined,
        capacity_label: form.capacity_label || undefined,
        pax: parseInt(form.pax) || undefined,
      });
      setMsg("Güncellendi!");
      setEditItem(null);
      load();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hata");
    }
    setSaving(false);
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    try {
      await axios.delete(`/inventory/${deleteConfirm.id}`);
      setDeleteConfirm(null);
      load();
    } catch { }
  };

  const handleBulkAvailability = async (e) => {
    e.preventDefault();
    if (!bulkModal) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await axios.post("/inventory/availability/bulk", {
        inventory_id: bulkModal.id,
        date_start: bulkForm.date_start,
        date_end: bulkForm.date_end,
        available_rooms: parseInt(bulkForm.available_rooms),
        price_per_night: bulkForm.price_per_night ? parseFloat(bulkForm.price_per_night) : null,
      });
      setMsg(res.data.message);
      setBulkModal(null);
      setBulkForm({ date_start: "", date_end: "", available_rooms: 0, price_per_night: "" });
      load();
      if (calendarItem && calendarItem.id === bulkModal.id) {
        loadCalendar(calendarItem.id, calendarMonth);
      }
    } catch (err) {
      setMsg(err.response?.data?.detail || "Hata");
    }
    setSaving(false);
  };

  const startEdit = (item) => {
    setEditItem(item);
    setForm({
      room_type: item.room_type,
      room_type_name: item.room_type_name,
      total_rooms: item.total_rooms,
      description: item.description || "",
      capacity_label: item.capacity_label || "",
      pax: item.pax || 2,
    });
  };

  const getDayColor = (day) => {
    if (!day.has_data) return "#f8fafc";
    const ratio = day.total_rooms > 0 ? day.booked_rooms / day.total_rooms : 0;
    if (ratio >= 1) return "#fee2e2";
    if (ratio >= 0.7) return "#fef3c7";
    if (ratio > 0) return "#dcfce7";
    return "#f0fdf4";
  };

  if (loading) return <Layout><div className="page-loading">Yükleniyor...</div></Layout>;

  return (
    <Layout>
      <div className="page-header">
        <h1>📦 Envanter Yönetimi</h1>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>+ Yeni Oda Tipi</button>
      </div>

      {msg && <div className="alert" style={{ marginBottom: "1rem" }}>{msg}</div>}

      {/* Özet Kartlar */}
      {summary && summary.items.length > 0 && (
        <div className="grid-3" style={{ marginBottom: "1.5rem" }}>
          {summary.items.map((s) => (
            <div key={s.inventory_id} className="card" style={{ padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <strong>{s.room_type_name}</strong>
                <span className="chip">{s.room_type}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.85rem" }}>
                <div>Toplam Oda: <strong>{s.total_rooms}</strong></div>
                <div>Bugün Müsait: <strong style={{ color: s.today_available > 0 ? "#166534" : "#991b1b" }}>{s.today_available}</strong></div>
                <div>Bugün Dolu: <strong>{s.today_booked}</strong></div>
                <div>Doluluk: <strong>{s.occupancy_rate}%</strong></div>
                {s.today_price && <div>Bugün Fiyat: <strong>{s.today_price}₺</strong></div>}
              </div>
              <div style={{ width: "100%", height: "6px", background: "#e2e8f0", borderRadius: "3px", marginTop: "0.5rem" }}>
                <div style={{
                  width: `${Math.min(s.occupancy_rate, 100)}%`,
                  height: "100%",
                  background: s.occupancy_rate > 80 ? "#ef4444" : s.occupancy_rate > 50 ? "#f59e0b" : "#22c55e",
                  borderRadius: "3px",
                  transition: "width 0.3s ease",
                }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Envanter Listesi */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <h3 style={{ marginBottom: "1rem" }}>Oda Tipleri ({items.length})</h3>
        {items.length === 0 ? (
          <div style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>
            Henüz envanter tanımı yok. Yeni oda tipi ekleyin.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Oda Tipi</th>
                  <th>Ad</th>
                  <th>Toplam</th>
                  <th>Kapasite</th>
                  <th>Kişi</th>
                  <th>İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td><span className="chip">{ROOM_TYPES_INV.find(r => r.value === item.room_type)?.label || item.room_type}</span></td>
                    <td><strong>{item.room_type_name}</strong></td>
                    <td>{item.total_rooms}</td>
                    <td>{item.capacity_label || "-"}</td>
                    <td>{item.pax || "-"}</td>
                    <td>
                      <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                        <button className="btn-secondary btn-sm" onClick={() => { setCalendarItem(item); }}>📅 Takvim</button>
                        <button className="btn-secondary btn-sm" onClick={() => setBulkModal(item)}>📋 Müsaitlik</button>
                        <button className="btn-secondary btn-sm" onClick={() => startEdit(item)}>✏️</button>
                        <button className="btn-danger btn-sm" onClick={() => setDeleteConfirm(item)}>🗑️</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Takvim Görünümü */}
      {calendarItem && calendarData && (
        <div className="card" style={{ padding: "1.25rem", marginTop: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h3>📅 {calendarData.room_type_name} - Takvim</h3>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <button className="btn-secondary btn-sm" onClick={() => {
                const [y, m] = calendarMonth.split("-").map(Number);
                const prev = m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
                setCalendarMonth(prev);
              }}>◀</button>
              <strong>{calendarMonth}</strong>
              <button className="btn-secondary btn-sm" onClick={() => {
                const [y, m] = calendarMonth.split("-").map(Number);
                const next = m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, "0")}`;
                setCalendarMonth(next);
              }}>▶</button>
              <button className="btn-ghost btn-sm" onClick={() => setCalendarItem(null)}>✕ Kapat</button>
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", fontSize: "0.75rem" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: "#f0fdf4", border: "1px solid #ccc" }} /> Boş
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: "#dcfce7", border: "1px solid #ccc" }} /> Müsait
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: "#fef3c7", border: "1px solid #ccc" }} /> Az Oda
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: "#fee2e2", border: "1px solid #ccc" }} /> Dolu
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "4px" }}>
            {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((d) => (
              <div key={d} style={{ textAlign: "center", fontWeight: 600, fontSize: "0.75rem", padding: "0.25rem", color: "#64748b" }}>{d}</div>
            ))}
            {calendarData.days.length > 0 && (() => {
              const firstDate = new Date(calendarData.days[0].date + "T00:00:00");
              const dayOfWeek = firstDate.getDay();
              const offset = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
              const blanks = Array(offset).fill(null);
              return [...blanks.map((_, i) => <div key={`b-${i}`} />), ...calendarData.days.map((day) => {
                const dayNum = new Date(day.date + "T00:00:00").getDate();
                return (
                  <div key={day.date} style={{
                    background: getDayColor(day),
                    border: "1px solid #e2e8f0",
                    borderRadius: "4px",
                    padding: "0.25rem",
                    textAlign: "center",
                    fontSize: "0.7rem",
                    minHeight: "52px",
                  }}>
                    <div style={{ fontWeight: 600, fontSize: "0.8rem" }}>{dayNum}</div>
                    {day.has_data ? (
                      <>
                        <div style={{ color: "#166534" }}>{day.available_rooms} müsait</div>
                        {day.price_per_night && <div style={{ color: "#7c3aed" }}>{day.price_per_night}₺</div>}
                      </>
                    ) : (
                      <div style={{ color: "#94a3b8" }}>-</div>
                    )}
                  </div>
                );
              })];
            })()}
          </div>
        </div>
      )}

      {/* Yeni Oda Tipi Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Yeni Oda Tipi Ekle">
        <form onSubmit={handleCreate}>
          <label className="field-label">Oda Tipi</label>
          <select className="field" value={form.room_type} onChange={(e) => setForm({ ...form, room_type: e.target.value })}>
            {ROOM_TYPES_INV.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <label className="field-label">Oda Adı</label>
          <input className="field" value={form.room_type_name} onChange={(e) => setForm({ ...form, room_type_name: e.target.value })} placeholder="Göl Manzaralı Bungalov" required />
          <label className="field-label">Toplam Oda Sayısı</label>
          <input className="field" type="number" min={1} value={form.total_rooms} onChange={(e) => setForm({ ...form, total_rooms: e.target.value })} required />
          <label className="field-label">Kapasite Etiketi (2+1, 3+1 vb.)</label>
          <input className="field" value={form.capacity_label} onChange={(e) => setForm({ ...form, capacity_label: e.target.value })} placeholder="2+1" />
          <label className="field-label">Kişi Sayısı</label>
          <input className="field" type="number" min={1} value={form.pax} onChange={(e) => setForm({ ...form, pax: e.target.value })} />
          <label className="field-label">Açıklama</label>
          <textarea className="field" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>İptal</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Kaydediliyor..." : "Kaydet"}</button>
          </div>
        </form>
      </Modal>

      {/* Düzenle Modal */}
      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Oda Tipini Düzenle">
        <form onSubmit={handleUpdate}>
          <label className="field-label">Oda Adı</label>
          <input className="field" value={form.room_type_name} onChange={(e) => setForm({ ...form, room_type_name: e.target.value })} required />
          <label className="field-label">Toplam Oda Sayısı</label>
          <input className="field" type="number" min={1} value={form.total_rooms} onChange={(e) => setForm({ ...form, total_rooms: e.target.value })} required />
          <label className="field-label">Kapasite Etiketi</label>
          <input className="field" value={form.capacity_label} onChange={(e) => setForm({ ...form, capacity_label: e.target.value })} />
          <label className="field-label">Kişi Sayısı</label>
          <input className="field" type="number" min={1} value={form.pax} onChange={(e) => setForm({ ...form, pax: e.target.value })} />
          <label className="field-label">Açıklama</label>
          <textarea className="field" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => setEditItem(null)}>İptal</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Kaydediliyor..." : "Güncelle"}</button>
          </div>
        </form>
      </Modal>

      {/* Toplu Müsaitlik Modal */}
      <Modal open={!!bulkModal} onClose={() => setBulkModal(null)} title={`Müsaitlik Ayarla — ${bulkModal?.room_type_name || ""}`}>
        <form onSubmit={handleBulkAvailability}>
          <label className="field-label">Başlangıç Tarihi</label>
          <input className="field" type="date" value={bulkForm.date_start} onChange={(e) => setBulkForm({ ...bulkForm, date_start: e.target.value })} required />
          <label className="field-label">Bitiş Tarihi</label>
          <input className="field" type="date" value={bulkForm.date_end} onChange={(e) => setBulkForm({ ...bulkForm, date_end: e.target.value })} required />
          <label className="field-label">Müsait Oda Sayısı (max: {bulkModal?.total_rooms})</label>
          <input className="field" type="number" min={0} max={bulkModal?.total_rooms || 99} value={bulkForm.available_rooms}
            onChange={(e) => setBulkForm({ ...bulkForm, available_rooms: e.target.value })} required />
          <label className="field-label">Gecelik Fiyat (₺, opsiyonel)</label>
          <input className="field" type="number" min={0} step="0.01" value={bulkForm.price_per_night}
            onChange={(e) => setBulkForm({ ...bulkForm, price_per_night: e.target.value })} placeholder="Boş bırakılabilir" />
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="btn-secondary" onClick={() => setBulkModal(null)}>İptal</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Kaydediliyor..." : "Uygula"}</button>
          </div>
        </form>
      </Modal>

      {/* Silme Onay */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Oda Tipini Sil"
        message={`"${deleteConfirm?.room_type_name}" oda tipini ve tüm müsaitlik verilerini silmek istediğinize emin misiniz?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Layout>
  );
};

export default InventoryPage;
