import PropTypes from 'prop-types';
import { formatDateTime, formatPrice, platformLabel, platformLogo } from '../utils/format';

export default function ListingList({ listings }) {
  return (
    <div className="flex flex-col gap-3">
      {listings.map((item) => {
        const logo = platformLogo(item.source);
        return (
          <a
            key={item.item_id}
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 rounded-xl p-3 transition hover:bg-[#f5f5f7]"
          >
            {logo && <img src={logo} alt="" className="h-11 w-11 rounded-lg object-contain" />}
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold">{item.title}</div>
              <div className="mt-1 text-xs text-[#86868b]">
                {platformLabel(item.source)} · {[item.sgg, item.emd].filter(Boolean).join(' ')} ·{' '}
                {formatDateTime(item.created_at)}
              </div>
            </div>
            <div className="shrink-0 text-right text-base font-extrabold">
              ₩{formatPrice(item.listing_price)}
            </div>
          </a>
        );
      })}
    </div>
  );
}

ListingList.propTypes = {
  listings: PropTypes.arrayOf(
    PropTypes.shape({
      item_id: PropTypes.number.isRequired,
      listing_price: PropTypes.number.isRequired,
      title: PropTypes.string.isRequired,
      source: PropTypes.string.isRequired,
      source_url: PropTypes.string.isRequired,
      sgg: PropTypes.string,
      emd: PropTypes.string,
      created_at: PropTypes.string,
    }),
  ).isRequired,
};
