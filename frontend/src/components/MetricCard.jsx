import PropTypes from 'prop-types';

export default function MetricCard({ label, value, tone = 'default', caption }) {
  const toneClass =
    tone === 'blue'
      ? 'text-[#0071e3]'
      : tone === 'red'
        ? 'text-red-500'
        : tone === 'green'
          ? 'text-emerald-600'
          : 'text-[#1d1d1f]';

  return (
    <div className="rounded-xl bg-[#f5f5f7] p-4">
      <div className="mb-2 text-xs font-semibold text-[#86868b] md:text-sm">{label}</div>
      <div className={`text-2xl font-extrabold md:text-3xl ${toneClass}`}>{value}</div>
      {caption && <div className="mt-2 text-xs text-[#86868b]">{caption}</div>}
    </div>
  );
}

MetricCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  tone: PropTypes.oneOf(['default', 'blue', 'red', 'green']),
  caption: PropTypes.string,
};
