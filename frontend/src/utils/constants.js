export const FEATURES_LIST = [
  "Jakuzili","Şömine","Isıtmalı soba","Göl manzarası","Dağ manzarası",
  "Özel bahçe","Havuz","Isıtmalı havuz","Barbekü alanı",
  "Evcil hayvan uygun","Otopark","Bebek karyolası","Engelli erişim","Spa",
  "Özel teras","Balkon","Mutfaklı","Film köşesi","Bisiklet kiralama",
];

export const ROOM_TYPES = [
  { value: "standart", label: "🛏 Standart Oda" },
  { value: "suite",    label: "🌟 Süit" },
  { value: "bungalov", label: "🏡 Bungalov" },
  { value: "villa",    label: "🏰 Villa" },
  { value: "apart",    label: "🏢 Apart" },
  { value: "dag_evi",  label: "⛰ Dağ Evi" },
  { value: "treehouse",label: "🌳 Ağaç Evi" },
  { value: "konteyner",label: "📦 Konteyner Oda" },
  { value: "cift_oda", label: "👫 Çift Kişilik Oda" },
  { value: "aile_oda", label: "👨‍👩‍👧 Aile Odası" },
];

export const GUEST_RESTRICTIONS_LIST = [
  "Sadece çift",
  "Sadece aile",
  "18 yaş üstü",
  "Evcil hayvan kabul edilmez",
  "Çocuk kabul edilmez",
  "Grup kabul edilmez",
  "Sigara içilmez",
  "Bekâr grubu kabul edilmez",
];

export const ROOM_TYPES_INV = [
  { value: "standart", label: "Standart Oda" },
  { value: "suite", label: "Suite" },
  { value: "bungalov", label: "Bungalov" },
  { value: "villa", label: "Villa" },
  { value: "apart", label: "Apart" },
  { value: "dag_evi", label: "Dağ Evi" },
  { value: "cadir", label: "Çadır/Glamping" },
  { value: "diger", label: "Diğer" },
];

export const RULE_TYPES = [
  { value: "seasonal", label: "Sezon", icon: "🌞" },
  { value: "weekend", label: "Hafta Sonu", icon: "📅" },
  { value: "occupancy", label: "Doluluk", icon: "📊" },
  { value: "early_bird", label: "Erken Rezervasyon", icon: "🐦" },
  { value: "last_minute", label: "Son Dakika", icon: "⏰" },
  { value: "holiday", label: "Tatil/Bayram", icon: "🎉" },
];

export const statusLabel = (s) => {
  const map = {
    pending: "Beklemede",
    accepted: "Kabul",
    rejected: "Red",
    alternative_offered: "Alternatif Sunuldu",
    cancelled: "İptal",
    available: "Müsait",
    limited: "Sınırlı",
    alternative: "Alternatif",
  };
  return map[s] || s;
};

export const roomTypeLabel = (val) => {
  const found = ROOM_TYPES.find((r) => r.value === val);
  return found ? found.label : val;
};
