export const formatPrice = (value) => {
  const number = Number(value || 0);
  return number.toLocaleString('ko-KR');
};

export const formatDate = (value) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).split('T')[0];
  return date.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' });
};

export const formatDateTime = (value) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const platformLabel = (source) => {
  if (source === 'daangn') return '당근';
  if (source === 'bunjang') return '번개장터';
  if (source === 'joongna') return '중고나라';
  return source || '기타';
};

export const platformLogo = (source) => {
  if (source === 'daangn') return '/carrot.png';
  if (source === 'bunjang') return '/bunjang.png';
  if (source === 'joongna') return '/nara.png';
  return null;
};
