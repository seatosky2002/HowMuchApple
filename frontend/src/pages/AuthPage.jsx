import PropTypes from 'prop-types';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { authApi, getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function AuthPage({ mode }) {
  const isRegister = mode === 'register';
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register } = useAuth();
  const [form, setForm] = useState({ email: '', password: '', nickname: '' });
  const [resetEmail, setResetEmail] = useState('');
  const [status, setStatus] = useState({ loading: false, error: '', message: '' });
  const from = location.state?.from || '/';

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus({ loading: true, error: '', message: '' });
    try {
      if (isRegister) {
        await register(form);
      } else {
        await login({ email: form.email, password: form.password });
      }
      navigate(from, { replace: true });
    } catch (err) {
      setStatus({
        loading: false,
        error: getErrorMessage(err, isRegister ? '회원가입에 실패했습니다.' : '로그인에 실패했습니다.'),
        message: '',
      });
    }
  };

  const requestReset = async () => {
    if (!resetEmail) {
      setStatus((prev) => ({ ...prev, error: '비밀번호 재설정 이메일을 입력해주세요.' }));
      return;
    }
    try {
      const { data } = await authApi.requestPasswordReset({ email: resetEmail });
      setStatus({ loading: false, error: '', message: data.message || '메일을 확인해주세요.' });
    } catch (err) {
      setStatus({ loading: false, error: getErrorMessage(err), message: '' });
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4 py-10">
      <div className="grid w-full max-w-[980px] overflow-hidden rounded-3xl border border-[#e8e8ed] bg-white shadow-sm md:grid-cols-[1fr_420px]">
        <section className="flex flex-col justify-between bg-[#f5f5f7] p-8 md:p-12">
          <div>
            <Link to="/" className="text-2xl font-extrabold tracking-tight">
              How Much, Apple
            </Link>
            <h1 className="mt-12 text-4xl font-extrabold tracking-tight md:text-5xl">
              가격 알림까지 이어지는 중고 시세 관리
            </h1>
            <p className="mt-5 text-base leading-7 text-[#6e6e73]">
              로그인하면 찜한 SKU의 희망 가격을 저장하고, 조건에 맞는 매물이 잡힐 때 알림을 받을 수 있습니다.
            </p>
          </div>
          <div className="mt-10 text-sm font-semibold text-[#86868b]">
            쿠키 기반 인증 · 이메일/SMS 알림 · watchlist 연동
          </div>
        </section>
        <section className="p-8 md:p-10">
          <h2 className="mb-6 text-3xl font-extrabold">{isRegister ? '회원가입' : '로그인'}</h2>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {isRegister && (
              <label>
                <span className="mb-2 block text-sm font-semibold text-[#86868b]">닉네임</span>
                <input
                  className="field"
                  value={form.nickname}
                  onChange={(event) => setForm((prev) => ({ ...prev, nickname: event.target.value }))}
                  minLength={2}
                  required
                />
              </label>
            )}
            <label>
              <span className="mb-2 block text-sm font-semibold text-[#86868b]">이메일</span>
              <input
                className="field"
                type="email"
                value={form.email}
                onChange={(event) => {
                  setForm((prev) => ({ ...prev, email: event.target.value }));
                  setResetEmail(event.target.value);
                }}
                required
              />
            </label>
            <label>
              <span className="mb-2 block text-sm font-semibold text-[#86868b]">비밀번호</span>
              <input
                className="field"
                type="password"
                value={form.password}
                onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                minLength={8}
                required
              />
            </label>
            {status.error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm font-semibold text-red-600">
                {status.error}
              </div>
            )}
            {status.message && (
              <div className="rounded-lg bg-blue-50 p-3 text-sm font-semibold text-[#0071e3]">
                {status.message}
              </div>
            )}
            <button className="btn-primary mt-2" type="submit" disabled={status.loading}>
              {status.loading ? '처리 중' : isRegister ? '가입하고 시작' : '로그인'}
            </button>
          </form>

          <div className="mt-6 text-sm text-[#86868b]">
            {isRegister ? '이미 계정이 있나요?' : '계정이 없나요?'}{' '}
            <Link className="font-bold text-[#0071e3]" to={isRegister ? '/login' : '/register'}>
              {isRegister ? '로그인' : '회원가입'}
            </Link>
          </div>

          {!isRegister && (
            <div className="mt-8 rounded-2xl bg-[#f5f5f7] p-4">
              <div className="mb-2 text-sm font-bold">비밀번호 재설정</div>
              <div className="flex gap-2">
                <input
                  className="field py-2"
                  type="email"
                  placeholder="email@example.com"
                  value={resetEmail}
                  onChange={(event) => setResetEmail(event.target.value)}
                />
                <button type="button" className="btn-secondary py-2" onClick={requestReset}>
                  발송
                </button>
              </div>
              <Link to="/password-reset" className="mt-3 inline-block text-xs font-bold text-[#0071e3]">
                재설정 토큰을 이미 받았습니다
              </Link>
            </div>
          )}

          <div className="mt-8 grid gap-2">
            <a className="btn-secondary text-center" href="/api/v1/auth/oauth/kakao/redirect">
              카카오로 계속하기
            </a>
            <a className="btn-secondary text-center" href="/api/v1/auth/oauth/apple/redirect">
              Apple로 계속하기
            </a>
          </div>
        </section>
      </div>
    </div>
  );
}

AuthPage.propTypes = {
  mode: PropTypes.oneOf(['login', 'register']).isRequired,
};
