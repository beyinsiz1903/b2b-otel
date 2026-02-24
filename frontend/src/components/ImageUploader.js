import React from "react";
import axios from "@/utils/api";

const ImageUploader = ({ value, onChange, label = "Resimler" }) => {
  const [uploading, setUploading] = React.useState(false);
  const [uploadError, setUploadError] = React.useState("");
  const [urlInput, setUrlInput] = React.useState("");
  const fileInputRef = React.useRef(null);

  // value → string (virgülle ayrılmış URL'ler)
  const urls = value ? value.split(",").map((s) => s.trim()).filter(Boolean) : [];

  const addUrl = (url) => {
    if (!url.trim()) return;
    if (urls.includes(url.trim())) return;
    onChange([...urls, url.trim()].join(", "));
    setUrlInput("");
  };

  const removeUrl = (idx) => {
    const next = urls.filter((_, i) => i !== idx);
    onChange(next.join(", "));
  };

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setUploading(true);
    setUploadError("");
    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        const res = await axios.post("/upload-image", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const fullUrl = `${process.env.REACT_APP_BACKEND_URL}/api/files/${res.data.filename}`;
        if (!urls.includes(fullUrl)) {
          urls.push(fullUrl);
        }
      }
      onChange(urls.join(", "));
    } catch (err) {
      setUploadError(err.response?.data?.detail || "Yükleme başarısız. Dosya JPG/PNG/WEBP olmalı, max 10 MB.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#374151", textTransform: "uppercase", letterSpacing: "0.03em" }}>
        {label}
      </span>

      {/* Önizleme */}
      {urls.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          {urls.map((url, i) => (
            <div key={i} style={{ position: "relative", width: 80, height: 64 }}>
              <img
                src={url}
                alt={`Resim ${i + 1}`}
                style={{ width: 80, height: 64, objectFit: "cover", borderRadius: "0.4rem", border: "1px solid #e2e8f0" }}
                onError={(e) => { e.target.style.display = "none"; }}
              />
              <button
                type="button"
                onClick={() => removeUrl(i)}
                style={{
                  position: "absolute", top: -6, right: -6,
                  width: 18, height: 18, borderRadius: "50%",
                  background: "#dc2626", color: "#fff",
                  border: "none", cursor: "pointer",
                  fontSize: "0.65rem", lineHeight: 1,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Dosya yükle butonu */}
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}
        >
          {uploading ? <><span className="loading-spin" style={{ width: 14, height: 14, borderWidth: 2 }} /> Yükleniyor...</> : "📁 Dosyadan Yükle"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp,image/gif"
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>JPG, PNG, WEBP — max 10 MB</span>
      </div>

      {/* URL ile ekle */}
      <div style={{ display: "flex", gap: "0.4rem" }}>
        <input
          type="url"
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addUrl(urlInput))}
          placeholder="veya URL yapıştırın: https://..."
          style={{
            flex: 1, borderRadius: "0.5rem", border: "1.5px solid #e2e8f0",
            padding: "0.5rem 0.75rem", fontSize: "0.875rem", background: "#fafafa",
          }}
        />
        <button type="button" className="btn-secondary btn-sm" onClick={() => addUrl(urlInput)}>
          Ekle
        </button>
      </div>

      {uploadError && <div className="error" style={{ fontSize: "0.8rem" }}>{uploadError}</div>}
      <div className="field-help">⚠️ Logo, tabela veya iletişim bilgisi görünen görseller kullanmayın.</div>
    </div>
  );

export default ImageUploader;
