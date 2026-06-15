import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { analyticsApi, getErrorMessage, skuApi, watchlistApi } from '../api/client';
import EmptyState from '../components/EmptyState';
import ListingList from '../components/ListingList';
import MetricCard from '../components/MetricCard';
import { useAuth } from '../context/AuthContext';
import { formatDate, formatPrice, platformLabel } from '../utils/format';

export default function MarketPage() {
  const { skuId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();
  const regionId = searchParams.get('region_id') || '';
  const sdId = searchParams.get('sd_id') || '';
  const page = Number(searchParams.get('page') || 1);
  const sort = searchParams.get('sort') || 'price_asc';
  const source = searchParams.get('source') || '';
  const [summary, setSummary] = useState(null);
  const [listings, setListings] = useState(null);
  const [regionPrices, setRegionPrices] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [watchForm, setWatchForm] = useState({ max_price: '', label: '', channels: ['email'] });
  const [status, setStatus] = useState({ loading: false, error: '', watchMessage: '' });

  const queryParams = useMemo(
    () => ({
      sku_id: Number(skuId),
      ...(regionId ? { region_id: Number(regionId) } : {}),
    }),
    [skuId, regionId],
  );

  useEffect(() => {
    if (!skuId) return;
    let alive = true;
    const load = async () => {
      setStatus((prev) => ({ ...prev, loading: true, error: '', watchMessage: '' }));
      try {
        const [summaryRes, listingsRes, regionPricesRes, platformsRes] = await Promise.all([
          analyticsApi.summary(queryParams),
          analyticsApi.listings({
            ...queryParams,
            page,
            page_size: 10,
            sort,
            ...(source ? { source } : {}),
          }),
          skuApi.regionPrices(skuId, { ...(sdId ? { sd_id: sdId } : {}), level: 'emd' }).catch(() => ({
            data: { regions: [] },
          })),
          analyticsApi.platformCompare(queryParams).catch(() => ({ data: { platforms: [] } })),
        ]);
        if (!alive) return;
        setSummary(summaryRes.data);
        setListings(listingsRes.data);
        setRegionPrices(regionPricesRes.data.regions || []);
        setPlatforms(platformsRes.data.platforms || []);
        setWatchForm((prev) => ({
          ...prev,
          max_price: prev.max_price || summaryRes.data?.summary?.min_price || '',
          label: prev.label || summaryRes.data?.label || '',
        }));
      } catch (err) {
        if (!alive) return;
        setStatus((prev) => ({
          ...prev,
          error: getErrorMessage(err, '시세 데이터를 불러오지 못했습니다.'),
        }));
      } finally {
        if (alive) setStatus((prev) => ({ ...prev, loading: false }));
      }
    };
    load();
    return () => {
      alive = false;
    };
  }, [skuId, queryParams, page, sort, source, sdId]);

  const updateParam = (key, value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.set('page', '1');
    setSearchParams(next);
  };

  const handleWatchSubmit = async (event) => {
    event.preventDefault();
    setStatus((prev) => ({ ...prev, watchMessage: '' }));
    try {
      await watchlistApi.create({
        sku_id: Number(skuId),
        region_id: regionId ? Number(regionId) : null,
        max_price: Number(watchForm.max_price),
        label: watchForm.label || summary?.label,
        alert_channels: watchForm.channels,
      });
      setStatus((prev) => ({ ...prev, watchMessage: '찜과 알림 조건을 저장했습니다.' }));
    } catch (err) {
      setStatus((prev) => ({
        ...prev,
        watchMessage: getErrorMessage(err, '찜을 저장하지 못했습니다.'),
      }));
    }
  };

  if (!skuId) {
    return (
      <EmptyState
        title="분석할 제품을 먼저 선택해주세요"
        body="검색 페이지에서 제품 스펙과 지역을 선택하면 새 분석 페이지로 이동합니다."
        action={
          <Link to="/" className="btn-primary inline-block">
            검색으로 이동
          </Link>
        }
      />
    );
  }

  if (status.loading && !summary) {
    return <div className="panel text-center">시세 데이터를 불러오는 중입니다.</div>;
  }

  if (status.error) {
    return <EmptyState title="데이터를 불러오지 못했습니다" body={status.error} />;
  }

  const chartData = summary?.price_trend?.chart_data || [];
  const regionalBreakdown = summary?.regional_breakdown || [];

  return (
    <div className="animate-fadeIn">
      <header className="mb-8">
        <div className="text-sm font-semibold text-[#86868b]">{summary?.region || '전체 지역'}</div>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight md:text-5xl">
          {summary?.label || `SKU ${skuId}`} 시세
        </h1>
      </header>

      <section className="mb-8 grid gap-4 md:grid-cols-4">
        <MetricCard label="평균 시세" value={`₩${formatPrice(summary?.summary?.avg_price)}`} tone="blue" />
        <MetricCard label="최저가" value={`₩${formatPrice(summary?.summary?.min_price)}`} />
        <MetricCard label="최고가" value={`₩${formatPrice(summary?.summary?.max_price)}`} />
        <MetricCard
          label="매물 수"
          value={`${summary?.summary?.listing_count || 0}개`}
          caption={formatDate(summary?.summary?.updated_at)}
        />
      </section>

      <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
        <div className="flex flex-col gap-8">
          <section className="surface">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-2xl font-bold">가격 변동 추이</h2>
              <span className="text-sm font-semibold text-[#86868b]">
                {summary?.price_trend?.period || '4w'} · {summary?.price_trend?.change_rate || 0}%
              </span>
            </div>
            <TrendChart data={chartData} />
          </section>

          <section className="surface">
            <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <h2 className="text-2xl font-bold">최저가 매물</h2>
              <div className="flex gap-2">
                <select className="field py-2" value={sort} onChange={(event) => updateParam('sort', event.target.value)}>
                  <option value="price_asc">가격 낮은 순</option>
                  <option value="price_desc">가격 높은 순</option>
                  <option value="newest">최신 순</option>
                </select>
                <select
                  className="field py-2"
                  value={source}
                  onChange={(event) => updateParam('source', event.target.value)}
                >
                  <option value="">전체</option>
                  <option value="daangn">당근</option>
                  <option value="bunjang">번개장터</option>
                  <option value="joongna">중고나라</option>
                </select>
              </div>
            </div>
            {listings?.listings?.length ? (
              <>
                <ListingList listings={listings.listings} />
                <div className="mt-5 flex items-center justify-between text-sm font-semibold text-[#86868b]">
                  <button className="btn-secondary py-2" disabled={page <= 1} onClick={() => updateParam('page', String(page - 1))}>
                    이전
                  </button>
                  <span>
                    {page} / {Math.max(1, Math.ceil((listings.total || 0) / (listings.page_size || 10)))}
                  </span>
                  <button
                    className="btn-secondary py-2"
                    disabled={page >= Math.ceil((listings.total || 0) / (listings.page_size || 10))}
                    onClick={() => updateParam('page', String(page + 1))}
                  >
                    다음
                  </button>
                </div>
              </>
            ) : (
              <EmptyState title="매물이 없습니다" body="크롤링 결과가 쌓이면 이 영역에 표시됩니다." />
            )}
          </section>

          <section className="surface">
            <h2 className="mb-5 text-2xl font-bold">읍면동별 상세 시세</h2>
            <RegionTable rows={regionalBreakdown.length ? regionalBreakdown : regionPrices} />
          </section>
        </div>

        <aside className="flex flex-col gap-6">
          <section className="surface">
            <h2 className="mb-5 text-2xl font-bold">플랫폼 비교</h2>
            <div className="flex flex-col gap-3">
              {platforms.length ? (
                platforms.map((platform) => (
                  <div key={platform.source} className="rounded-xl bg-[#f5f5f7] p-4">
                    <div className="flex justify-between text-sm font-bold">
                      <span>{platformLabel(platform.source)}</span>
                      <span>₩{formatPrice(platform.avg_price)}</span>
                    </div>
                    <div className="mt-1 text-xs text-[#86868b]">{platform.listing_count}개 매물</div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-[#86868b]">플랫폼 통계가 아직 없습니다.</div>
              )}
            </div>
          </section>

          <section className="surface">
            <h2 className="mb-5 text-2xl font-bold">가격 알림</h2>
            {isAuthenticated ? (
              <form onSubmit={handleWatchSubmit} className="flex flex-col gap-4">
                <label>
                  <span className="mb-2 block text-sm font-semibold text-[#86868b]">알림 이름</span>
                  <input
                    className="field"
                    value={watchForm.label}
                    onChange={(event) => setWatchForm((prev) => ({ ...prev, label: event.target.value }))}
                  />
                </label>
                <label>
                  <span className="mb-2 block text-sm font-semibold text-[#86868b]">희망 가격</span>
                  <input
                    className="field"
                    type="number"
                    min="1"
                    value={watchForm.max_price}
                    onChange={(event) => setWatchForm((prev) => ({ ...prev, max_price: event.target.value }))}
                  />
                </label>
                <div className="flex gap-4 text-sm font-semibold">
                  {['email', 'sms'].map((channel) => (
                    <label key={channel} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={watchForm.channels.includes(channel)}
                        onChange={(event) =>
                          setWatchForm((prev) => ({
                            ...prev,
                            channels: event.target.checked
                              ? [...new Set([...prev.channels, channel])]
                              : prev.channels.filter((item) => item !== channel),
                          }))
                        }
                      />
                      {channel === 'email' ? '이메일' : 'SMS'}
                    </label>
                  ))}
                </div>
                <button className="btn-primary" type="submit">
                  찜에 추가
                </button>
                {status.watchMessage && <div className="text-sm font-semibold text-[#0071e3]">{status.watchMessage}</div>}
              </form>
            ) : (
              <EmptyState
                title="로그인이 필요합니다"
                body="가격 알림과 찜 기능은 로그인 후 사용할 수 있습니다."
                action={
                  <Link to="/login" className="btn-primary inline-block">
                    로그인
                  </Link>
                }
              />
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function TrendChart({ data }) {
  if (!data.length) {
    return <EmptyState title="추이 데이터 없음" body="가격 통계가 쌓이면 차트가 표시됩니다." />;
  }
  const values = data.map((item) => Number(item.avg_price || 0));
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || max || 1;
  const points = data.map((item, index) => {
    const x = 40 + (index / Math.max(1, data.length - 1)) * 520;
    const y = 150 - ((Number(item.avg_price) - min) / range) * 110;
    return { ...item, x, y };
  });

  return (
    <div className="rounded-xl bg-[#f5f5f7] p-4">
      <svg viewBox="0 0 600 180" className="h-[220px] w-full">
        <polyline
          points={points.map((point) => `${point.x},${point.y}`).join(' ')}
          fill="none"
          stroke="#1d1d1f"
          strokeWidth="3"
        />
        {points.map((point) => (
          <g key={point.bucket_ts}>
            <circle cx={point.x} cy={point.y} r="5" fill="#0071e3" />
            <text x={point.x} y="172" textAnchor="middle" fontSize="11" fill="#86868b">
              {formatDate(point.bucket_ts)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function RegionTable({ rows }) {
  if (!rows.length) {
    return <EmptyState title="지역 데이터 없음" body="지역별 통계가 생성되면 표가 표시됩니다." />;
  }
  const normalized = rows.map((row) => ({
    name: row.emd || row.name,
    sgg: row.sgg,
    avg_price: row.avg_price,
    listing_count: row.listing_count,
  }));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] border-collapse text-left">
        <thead>
          <tr className="border-b border-[#d2d2d7] text-xs font-bold text-[#86868b] uppercase">
            <th className="py-3">지역</th>
            <th className="py-3">평균가</th>
            <th className="py-3">매물 수</th>
          </tr>
        </thead>
        <tbody>
          {normalized
            .sort((a, b) => Number(a.avg_price) - Number(b.avg_price))
            .map((row) => (
              <tr key={`${row.sgg || ''}-${row.name}`} className="border-b border-[#f5f5f7]">
                <td className="py-3 font-semibold">
                  {[row.sgg, row.name].filter(Boolean).join(' ')}
                </td>
                <td className="py-3">₩{formatPrice(row.avg_price)}</td>
                <td className="py-3">{row.listing_count}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
