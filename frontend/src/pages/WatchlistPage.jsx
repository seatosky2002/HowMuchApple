import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getErrorMessage, watchlistApi } from '../api/client';
import EmptyState from '../components/EmptyState';
import { formatDateTime, formatPrice } from '../utils/format';

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState([]);
  const [selected, setSelected] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState({ loading: true, error: '', message: '' });

  const load = async () => {
    setStatus((prev) => ({ ...prev, loading: true, error: '' }));
    try {
      const { data } = await watchlistApi.list();
      setWatchlist(data.watchlist || []);
      setStatus((prev) => ({ ...prev, loading: false }));
    } catch (err) {
      setStatus({ loading: false, message: '', error: getErrorMessage(err) });
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openAlerts = async (watch) => {
    setSelected(watch);
    try {
      const { data } = await watchlistApi.alerts(watch.watch_id, { page_size: 10 });
      setAlerts(data.alerts || []);
    } catch (err) {
      setStatus((prev) => ({ ...prev, error: getErrorMessage(err) }));
    }
  };

  const toggle = async (watchId) => {
    try {
      await watchlistApi.toggle(watchId);
      await load();
    } catch (err) {
      setStatus((prev) => ({ ...prev, error: getErrorMessage(err) }));
    }
  };

  const remove = async (watchId) => {
    try {
      await watchlistApi.remove(watchId);
      setSelected(null);
      setAlerts([]);
      await load();
    } catch (err) {
      setStatus((prev) => ({ ...prev, error: getErrorMessage(err) }));
    }
  };

  return (
    <div className="animate-fadeIn">
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight">찜과 가격 알림</h1>
          <p className="mt-2 text-[#86868b]">희망 가격 이하 매물이 생기면 알림으로 받을 조건입니다.</p>
        </div>
        <Link to="/" className="btn-primary text-center">
          새 조건 만들기
        </Link>
      </header>

      {(status.error || status.message) && (
        <div
          className={`mb-6 rounded-xl p-4 text-sm font-semibold ${
            status.error ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-[#0071e3]'
          }`}
        >
          {status.error || status.message}
        </div>
      )}

      {status.loading ? (
        <div className="panel text-center">찜 목록을 불러오는 중입니다.</div>
      ) : !watchlist.length ? (
        <EmptyState
          title="저장한 찜이 없습니다"
          body="시세 페이지에서 원하는 가격 조건을 저장하면 이곳에서 관리할 수 있습니다."
          action={
            <Link to="/" className="btn-primary inline-block">
              제품 검색
            </Link>
          }
        />
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1fr_420px]">
          <section className="flex flex-col gap-4">
            {watchlist.map((watch) => (
              <article key={watch.watch_id} className="surface">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="text-sm font-semibold text-[#86868b]">{watch.product}</div>
                    <h2 className="mt-1 text-xl font-extrabold">{watch.label || watch.spec_label}</h2>
                    <div className="mt-2 text-sm text-[#86868b]">
                      {watch.region ? Object.values(watch.region).filter(Boolean).join(' ') : '전체 지역'} ·{' '}
                      {watch.alert_channels.join(', ')}
                    </div>
                  </div>
                  <div className="text-left md:text-right">
                    <div className="text-sm font-semibold text-[#86868b]">희망 가격</div>
                    <div className="text-2xl font-extrabold text-[#0071e3]">
                      ₩{formatPrice(watch.max_price)}
                    </div>
                  </div>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <button className="btn-secondary py-2" type="button" onClick={() => openAlerts(watch)}>
                    알림 보기
                  </button>
                  <button className="btn-secondary py-2" type="button" onClick={() => toggle(watch.watch_id)}>
                    {watch.is_active ? '비활성화' : '활성화'}
                  </button>
                  <button className="btn-secondary py-2" type="button" onClick={() => remove(watch.watch_id)}>
                    삭제
                  </button>
                  <Link className="btn-secondary py-2" to={`/market/${watch.sku_id}`}>
                    시세 보기
                  </Link>
                </div>
                {watch.latest_alert && (
                  <div className="mt-4 rounded-xl bg-[#f5f5f7] p-3 text-sm text-[#86868b]">
                    최근 알림: {formatDateTime(watch.latest_alert.triggered_at)} ·{' '}
                    {watch.latest_alert.is_read ? '읽음' : '안 읽음'}
                  </div>
                )}
              </article>
            ))}
          </section>

          <aside className="surface h-fit">
            <h2 className="mb-5 text-2xl font-bold">조건별 알림</h2>
            {!selected ? (
              <div className="text-sm text-[#86868b]">왼쪽에서 알림 보기를 선택하세요.</div>
            ) : (
              <>
                <div className="mb-4 rounded-xl bg-[#f5f5f7] p-4">
                  <div className="text-sm font-bold">{selected.label || selected.spec_label}</div>
                  <div className="mt-1 text-xs text-[#86868b]">watch_id {selected.watch_id}</div>
                </div>
                <div className="flex flex-col gap-3">
                  {alerts.length ? (
                    alerts.map((alert) => (
                      <div key={alert.alert_id} className="rounded-xl border border-[#e8e8ed] p-4">
                        <div className="text-sm font-semibold">{alert.message}</div>
                        <div className="mt-2 text-xs text-[#86868b]">
                          {formatDateTime(alert.triggered_at)} ·{' '}
                          {alert.listing_price ? `₩${formatPrice(alert.listing_price)}` : '매물 정보 없음'}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-[#86868b]">아직 발생한 알림이 없습니다.</div>
                  )}
                </div>
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
