import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { analyticsApi, catalogApi, getErrorMessage, regionApi, skuApi } from '../api/client';
import EmptyState from '../components/EmptyState';
import { formatPrice } from '../utils/format';

export default function HomePage() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState('');
  const [categoryDetail, setCategoryDetail] = useState(null);
  const [selectedOptions, setSelectedOptions] = useState({});
  const [regions, setRegions] = useState([]);
  const [sggList, setSggList] = useState([]);
  const [emdList, setEmdList] = useState([]);
  const [selectedSdId, setSelectedSdId] = useState('');
  const [selectedSggId, setSelectedSggId] = useState('');
  const [selectedRegionId, setSelectedRegionId] = useState('');
  const [trending, setTrending] = useState([]);
  const [popular, setPopular] = useState([]);
  const [status, setStatus] = useState({ loading: true, submitting: false, error: '' });

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [categoryRes, regionRes, trendingRes, popularRes] = await Promise.all([
          catalogApi.categories(),
          regionApi.sd(),
          analyticsApi.trending({ limit: 6, direction: 'both' }).catch(() => ({ data: { trending: [] } })),
          analyticsApi.popular({ limit: 6 }).catch(() => ({ data: { popular: [] } })),
        ]);
        if (!alive) return;
        const loadedCategories = categoryRes.data.categories || [];
        const loadedRegions = regionRes.data.regions || [];
        setCategories(loadedCategories);
        setRegions(loadedRegions);
        setTrending(trendingRes.data.trending || []);
        setPopular(popularRes.data.popular || []);
        setSelectedCategoryId(String(loadedCategories[0]?.category_id || ''));
        const seoul = loadedRegions.find((item) => item.name === '서울특별시') || loadedRegions[0];
        setSelectedSdId(String(seoul?.sd_id || ''));
        setStatus((prev) => ({ ...prev, loading: false, error: '' }));
      } catch (err) {
        if (!alive) return;
        setStatus((prev) => ({
          ...prev,
          loading: false,
          error: getErrorMessage(err, '초기 데이터를 불러오지 못했습니다.'),
        }));
      }
    };
    load();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCategoryId) return;
    let alive = true;
    const loadAttributes = async () => {
      try {
        const { data } = await catalogApi.attributes(selectedCategoryId);
        if (!alive) return;
        setCategoryDetail(data);
        setSelectedOptions({});
      } catch (err) {
        if (!alive) return;
        setStatus((prev) => ({
          ...prev,
          error: getErrorMessage(err, '카테고리 속성을 불러오지 못했습니다.'),
        }));
      }
    };
    loadAttributes();
    return () => {
      alive = false;
    };
  }, [selectedCategoryId]);

  useEffect(() => {
    if (!selectedSdId) return;
    let alive = true;
    const loadSgg = async () => {
      const { data } = await regionApi.sgg(selectedSdId);
      if (!alive) return;
      setSggList(data.sgg || []);
      setSelectedSggId('');
      setSelectedRegionId('');
      setEmdList([]);
    };
    loadSgg().catch(() => setSggList([]));
    return () => {
      alive = false;
    };
  }, [selectedSdId]);

  useEffect(() => {
    if (!selectedSggId) {
      setEmdList([]);
      setSelectedRegionId('');
      return;
    }
    let alive = true;
    const loadEmd = async () => {
      const { data } = await regionApi.emd(selectedSggId);
      if (!alive) return;
      setEmdList(data.emd || []);
      setSelectedRegionId('');
    };
    loadEmd().catch(() => setEmdList([]));
    return () => {
      alive = false;
    };
  }, [selectedSggId]);

  const selectedCategory = useMemo(
    () => categories.find((category) => String(category.category_id) === String(selectedCategoryId)),
    [categories, selectedCategoryId],
  );

  const requiredAttributes = categoryDetail?.attributes?.filter((attr) => attr.is_required) || [];
  const optionalAttributes = categoryDetail?.attributes?.filter((attr) => !attr.is_required) || [];

  const handleOptionChange = (attributeId, optionId) => {
    setSelectedOptions((prev) => ({ ...prev, [attributeId]: optionId }));
  };

  const buildAttributesPayload = () =>
    (categoryDetail?.attributes || [])
      .filter((attr) => selectedOptions[attr.attribute_id])
      .map((attr) => ({
        attribute_id: Number(attr.attribute_id),
        option_id: Number(selectedOptions[attr.attribute_id]),
      }));

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus((prev) => ({ ...prev, submitting: true, error: '' }));
    try {
      const missing = requiredAttributes.filter((attr) => !selectedOptions[attr.attribute_id]);
      if (missing.length) {
        throw new Error(`${missing.map((attr) => attr.label).join(', ')}을 선택해주세요.`);
      }

      const { data } = await skuApi.resolve({
        category_id: Number(selectedCategoryId),
        attributes: buildAttributesPayload(),
      });
      const params = new URLSearchParams();
      if (selectedRegionId) params.set('region_id', selectedRegionId);
      if (selectedSdId) params.set('sd_id', selectedSdId);
      navigate(`/market/${data.sku_id}?${params.toString()}`);
    } catch (err) {
      setStatus((prev) => ({
        ...prev,
        error: getErrorMessage(err, err.message || 'SKU를 생성하지 못했습니다.'),
      }));
    } finally {
      setStatus((prev) => ({ ...prev, submitting: false }));
    }
  };

  const renderAttributeSelect = (attr) => (
    <label key={attr.attribute_id} className="block">
      <span className="mb-2 block text-left text-sm font-semibold text-[#86868b]">
        {attr.label}
        {attr.is_required && <span className="text-red-500"> *</span>}
      </span>
      <select
        className="field"
        value={selectedOptions[attr.attribute_id] || ''}
        onChange={(event) => handleOptionChange(attr.attribute_id, event.target.value)}
        disabled={!attr.options?.length}
      >
        <option value="">선택</option>
        {(attr.options || []).map((option) => (
          <option key={option.option_id} value={option.option_id}>
            {option.value}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="animate-fadeIn">
      <section className="mx-auto grid max-w-[1120px] items-start gap-8 py-6 md:grid-cols-[1fr_380px] md:py-12">
        <div>
          <h1 className="mb-5 text-center text-[3.2rem] leading-none font-extrabold tracking-tight md:text-left md:text-[4.8rem]">
            How Much, Apple
          </h1>
          <p className="mx-auto mb-10 max-w-[640px] text-center text-lg leading-8 text-[#86868b] md:mx-0 md:text-left">
            중고 Apple 제품의 시세, 지역별 매물, 알림 조건까지 한 흐름에서 관리합니다.
          </p>
          <form onSubmit={handleSubmit} className="surface flex flex-col gap-5">
            <div className="grid gap-4 md:grid-cols-[180px_1fr]">
              <label>
                <span className="mb-2 block text-left text-sm font-semibold text-[#86868b]">
                  카테고리
                </span>
                <select
                  className="field"
                  value={selectedCategoryId}
                  onChange={(event) => setSelectedCategoryId(event.target.value)}
                  disabled={status.loading}
                >
                  {categories.map((category) => (
                    <option key={category.category_id} value={category.category_id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="rounded-xl bg-[#f5f5f7] p-4">
                <div className="text-sm font-semibold text-[#86868b]">선택 중</div>
                <div className="mt-1 text-2xl font-extrabold">{selectedCategory?.name || '-'}</div>
              </div>
            </div>

            {status.loading ? (
              <div className="panel text-center text-sm text-[#86868b]">제품 정보를 불러오는 중입니다.</div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  {requiredAttributes.map(renderAttributeSelect)}
                </div>
                {optionalAttributes.length > 0 && (
                  <div>
                    <div className="mb-3 text-left text-sm font-semibold text-[#86868b]">
                      선택 옵션
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      {optionalAttributes.map(renderAttributeSelect)}
                    </div>
                  </div>
                )}
              </>
            )}

            <div>
              <div className="mb-3 text-left text-sm font-semibold text-[#86868b]">거래 지역</div>
              <div className="grid gap-4 md:grid-cols-3">
                <select
                  className="field"
                  value={selectedSdId}
                  onChange={(event) => setSelectedSdId(event.target.value)}
                >
                  <option value="">시/도 전체</option>
                  {regions.map((sd) => (
                    <option key={sd.sd_id} value={sd.sd_id}>
                      {sd.name}
                    </option>
                  ))}
                </select>
                <select
                  className="field"
                  value={selectedSggId}
                  onChange={(event) => setSelectedSggId(event.target.value)}
                  disabled={!selectedSdId}
                >
                  <option value="">시/군/구 전체</option>
                  {sggList.map((sgg) => (
                    <option key={sgg.sgg_id} value={sgg.sgg_id}>
                      {sgg.name}
                    </option>
                  ))}
                </select>
                <select
                  className="field"
                  value={selectedRegionId}
                  onChange={(event) => setSelectedRegionId(event.target.value)}
                  disabled={!selectedSggId}
                >
                  <option value="">읍/면/동 전체</option>
                  {emdList.map((emd) => (
                    <option key={emd.region_id} value={emd.region_id}>
                      {emd.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {status.error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm font-semibold text-red-600">
                {status.error}
              </div>
            )}
            <button type="submit" className="btn-primary" disabled={status.submitting || status.loading}>
              {status.submitting ? '분석 준비 중' : 'ANALYZE'}
            </button>
          </form>
        </div>

        <aside className="flex flex-col gap-5">
          <FeedPanel title="급등락 SKU" items={trending} kind="trending" />
          <FeedPanel title="인기 스펙" items={popular} kind="popular" />
        </aside>
      </section>
    </div>
  );
}

function FeedPanel({ title, items, kind }) {
  return (
    <section className="surface">
      <h2 className="mb-4 text-xl font-bold">{title}</h2>
      {!items.length ? (
        <EmptyState title="데이터 없음" body="크롤링과 통계 집계가 끝나면 이 영역에 표시됩니다." />
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <div key={`${kind}-${item.sku_id}`} className="rounded-xl bg-[#f5f5f7] p-4">
              <div className="text-sm font-bold">{item.label}</div>
              <div className="mt-2 flex items-center justify-between text-xs text-[#86868b]">
                <span>₩{formatPrice(item.avg_price)}</span>
                <span>
                  {kind === 'trending'
                    ? `${item.direction === 'rise' ? '상승' : '하락'} ${Math.abs(item.change_rate)}%`
                    : `검색 ${item.search_count}회`}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

FeedPanel.propTypes = {
  title: PropTypes.string.isRequired,
  kind: PropTypes.oneOf(['trending', 'popular']).isRequired,
  items: PropTypes.arrayOf(
    PropTypes.shape({
      sku_id: PropTypes.number.isRequired,
      label: PropTypes.string.isRequired,
      avg_price: PropTypes.number,
      direction: PropTypes.string,
      change_rate: PropTypes.number,
      search_count: PropTypes.number,
    }),
  ).isRequired,
};
