import { useEffect, useState } from 'react';
import { alertsApi, getErrorMessage } from '../api/client';
import EmptyState from '../components/EmptyState';
import { formatDateTime, formatPrice, platformLabel } from '../utils/format';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [meta, setMeta] = useState({ total: 0, unread: 0 });
  const [filter, setFilter] = useState('all');
  const [status, setStatus] = useState({ loading: true, error: '', message: '' });

  const load = async () => {
    setStatus((prev) => ({ ...prev, loading: true, error: '' }));
    try {
      const params = filter === 'unread' ? { is_read: false } : {};
      const { data } = await alertsApi.list({ ...params, page_size: 50 });
      setAlerts(data.alerts || []);
      setMeta({ total: data.total || 0, unread: data.unread || 0 });
      setStatus((prev) => ({ ...prev, loading: false }));
    } catch (err) {
      setStatus({ loading: false, message: '', error: getErrorMessage(err) });
    }
  };

  useEffect(() => {
    load();
  }, [filter]);

  const markRead = async (alertId) => {
    try {
      await alertsApi.markRead(alertId);
      await load();
    } catch (err) {
      setStatus((prev) => ({ ...prev, error: getErrorMessage(err) }));
    }
  };

  const markAllRead = async () => {
    try {
      const { data } = await alertsApi.markAllRead();
      setStatus((prev) => ({ ...prev, message: data.message || '전체 읽음 처리했습니다.' }));
      await load();
    } catch (err) {
      setStatus((prev) => ({ ...prev, error: getErrorMessage(err) }));
    }
  };

  const remove = async (alertId) => {
    try {
      await alertsApi.remove(alertId);
      await load();
    } catch (err) {
      setStatus((prev) => ({ ...prev, error: getErrorMessage(err) }));
    }
  };

  return (
    <div className="animate-fadeIn">
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight">알림</h1>
          <p className="mt-2 text-[#86868b]">
            전체 {meta.total}개 · 읽지 않음 {meta.unread}개
          </p>
        </div>
        <div className="flex gap-2">
          <select className="field py-2" value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="all">전체</option>
            <option value="unread">읽지 않음</option>
          </select>
          <button className="btn-primary py-2" type="button" onClick={markAllRead}>
            전체 읽음
          </button>
        </div>
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
        <div className="panel text-center">알림을 불러오는 중입니다.</div>
      ) : !alerts.length ? (
        <EmptyState title="알림이 없습니다" body="찜 조건에 맞는 매물이 잡히면 이곳에 표시됩니다." />
      ) : (
        <section className="flex flex-col gap-3">
          {alerts.map((alert) => (
            <article
              key={alert.alert_id}
              className={`surface ${alert.is_read ? '' : 'border-[#0071e3] bg-blue-50/20'}`}
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="text-sm font-semibold text-[#86868b]">
                    {alert.watch_label || alert.spec_label} · {formatDateTime(alert.triggered_at)}
                  </div>
                  <h2 className="mt-2 text-lg font-bold">{alert.message}</h2>
                  {alert.item && (
                    <div className="mt-2 text-sm text-[#86868b]">
                      {platformLabel(alert.item.source)} · ₩{formatPrice(alert.item.listing_price)}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {alert.item?.source_url && (
                    <a className="btn-secondary py-2" href={alert.item.source_url} target="_blank" rel="noreferrer">
                      매물 보기
                    </a>
                  )}
                  {!alert.is_read && (
                    <button className="btn-secondary py-2" type="button" onClick={() => markRead(alert.alert_id)}>
                      읽음
                    </button>
                  )}
                  <button className="btn-secondary py-2" type="button" onClick={() => remove(alert.alert_id)}>
                    삭제
                  </button>
                </div>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
