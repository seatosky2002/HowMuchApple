import PropTypes from 'prop-types';

export default function EmptyState({ title, body, action }) {
  return (
    <div className="rounded-2xl border border-dashed border-[#d2d2d7] p-8 text-center">
      <h3 className="mb-2 text-xl font-bold">{title}</h3>
      {body && <p className="mx-auto max-w-[520px] text-sm leading-6 text-[#86868b]">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

EmptyState.propTypes = {
  title: PropTypes.string.isRequired,
  body: PropTypes.string,
  action: PropTypes.node,
};
