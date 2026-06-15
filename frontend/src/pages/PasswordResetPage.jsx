import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { authApi, getErrorMessage } from '../api/client';

export default function PasswordResetPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({
    token: searchParams.get('token') || '',
    new_password: '',
  });
  const [status, setStatus] = useState({ loading: false, error: '', message: '' });

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus({ loading: true, error: '', message: '' });
    try {
      const { data } = await authApi.confirmPasswordReset(form);
      setStatus({ loading: false, error: '', message: data.message || '비밀번호가 변경되었습니다.' });
      setTimeout(() => navigate('/login'), 800);
    } catch (err) {
      setStatus({ loading: false, message: '', error: getErrorMessage(err) });
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4 py-10">
      <section className="w-full max-w-[460px] rounded-3xl border border-[#e8e8ed] bg-white p-8 shadow-sm">
        <Link to="/" className="text-xl font-extrabold tracking-tight">
          How Much, Apple
        </Link>
        <h1 className="mt-10 mb-6 text-3xl font-extrabold">비밀번호 재설정</h1>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label>
            <span className="mb-2 block text-sm font-semibold text-[#86868b]">토큰</span>
            <input
              className="field"
              value={form.token}
              onChange={(event) => setForm((prev) => ({ ...prev, token: event.target.value }))}
              required
            />
          </label>
          <label>
            <span className="mb-2 block text-sm font-semibold text-[#86868b]">새 비밀번호</span>
            <input
              className="field"
              type="password"
              minLength={8}
              value={form.new_password}
              onChange={(event) => setForm((prev) => ({ ...prev, new_password: event.target.value }))}
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
          <button className="btn-primary" type="submit" disabled={status.loading}>
            {status.loading ? '변경 중' : '비밀번호 변경'}
          </button>
        </form>
      </section>
    </div>
  );
}
