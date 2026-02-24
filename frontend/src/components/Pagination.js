import React from "react";

const Pagination = ({ total, skip, limit, onChange }) => {
  if (!total || total <= limit) return null;
  const pages = Math.ceil(total / limit);
  const currentPage = Math.floor(skip / limit) + 1;
  const maxVisible = 5;
  let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
  let endPage = Math.min(pages, startPage + maxVisible - 1);
  if (endPage - startPage < maxVisible - 1) startPage = Math.max(1, endPage - maxVisible + 1);

  return (
    <div className="pagination">
      <button className="pagination-btn" disabled={currentPage === 1} onClick={() => onChange(0)}>«</button>
      <button className="pagination-btn" disabled={currentPage === 1} onClick={() => onChange((currentPage - 2) * limit)}>‹</button>
      {Array.from({ length: endPage - startPage + 1 }, (_, i) => startPage + i).map((p) => (
        <button key={p} className={`pagination-btn ${p === currentPage ? "active" : ""}`} onClick={() => onChange((p - 1) * limit)}>
          {p}
        </button>
      ))}
      <button className="pagination-btn" disabled={currentPage === pages} onClick={() => onChange(currentPage * limit)}>›</button>
      <button className="pagination-btn" disabled={currentPage === pages} onClick={() => onChange((pages - 1) * limit)}>»</button>
      <span className="pagination-info">Toplam {total} kayıt</span>
    </div>
  );
};

export default Pagination;
