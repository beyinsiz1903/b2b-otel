import React from "react";

export const Skeleton = ({ width = "100%", height = "1rem", style = {}, count = 1 }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
    {Array.from({ length: count }).map((_, i) => (
      <div key={i} className="skeleton-box" style={{ width, height, borderRadius: "0.4rem", ...style }} />
    ))}
  </div>
);

export const SkeletonCard = () => (
  <div className="card" style={{ padding: "1.25rem" }}>
    <Skeleton height="1.2rem" width="60%" />
    <Skeleton height="0.85rem" width="80%" style={{ marginTop: "0.75rem" }} />
    <Skeleton height="0.85rem" width="40%" style={{ marginTop: "0.5rem" }} />
    <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
      <Skeleton height="2rem" width="5rem" />
      <Skeleton height="2rem" width="5rem" />
    </div>
  </div>
);

export default Skeleton;
