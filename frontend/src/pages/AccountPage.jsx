import { useEffect, useState } from 'react';
import { getErrorMessage, userApi, verificationApi } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { formatDateTime } from '../utils/format';

export default function AccountPage() {
  const { user, reloadUser } = useAuth();
  const [nickname, setNickname] = useState(user?.nickname || '');
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' });
  const [settings, setSettings] = useState(null);
  const [verify, setVerify] = useState({ emailCode: '', phone: user?.phone || '', phoneCode: '' });
  const [status, setStatus] = useState({ loading: true, message: '', error: '' });

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await userApi.getNotificationSettings();
        if (!alive) return;
        setSettings({
          channels: data.channels || { email: true, sms: false },
          dnd: {
            enabled: Boolean(data.dnd?.enabled),
            start: data.dnd?.start || '22:00',
            end: data.dnd?.end || '07:00',
          },
          watchlist_alerts_enabled: data.watchlist_alerts_enabled,
        });
      } catch (err) {
        if (!alive) return;
        setStatus((prev) => ({ ...prev, error: getErrorMessage(err) }));
      } finally {
        if (alive) setStatus((prev) => ({ ...prev, loading: false }));
      }
    };
    load();
    return () => {
      alive = false;
    };
  }, []);

  const showMessage = (message) => setStatus({ loading: false, error: '', message });
  const showError = (err) => setStatus({ loading: false, message: '', error: getErrorMessage(err) });

  const updateProfile = async (event) => {
    event.preventDefault();
    try {
      await userApi.updateMe({ nickname });
      await reloadUser();
      showMessage('프로필을 저장했습니다.');
    } catch (err) {
      showError(err);
    }
  };

  const changePassword = async (event) => {
    event.preventDefault();
    try {
      const { data } = await userApi.changePassword(passwords);
      setPasswords({ current_password: '', new_password: '' });
      showMessage(data.message || '비밀번호가 변경되었습니다.');
    } catch (err) {
      showError(err);
    }
  };

  const saveSettings = async () => {
    try {
      const payload = {
        channels: settings.channels,
        dnd: {
          enabled: settings.dnd.enabled,
          start: settings.dnd.enabled ? settings.dnd.start : null,
          end: settings.dnd.enabled ? settings.dnd.end : null,
        },
        watchlist_alerts_enabled: settings.watchlist_alerts_enabled,
      };
      const { data } = await userApi.updateNotificationSettings(payload);
      setSettings({
        channels: data.channels,
        dnd: {
          enabled: Boolean(data.dnd?.enabled),
          start: data.dnd?.start || '22:00',
          end: data.dnd?.end || '07:00',
        },
        watchlist_alerts_enabled: data.watchlist_alerts_enabled,
      });
      showMessage('알림 설정을 저장했습니다.');
    } catch (err) {
      showError(err);
    }
  };

  const sendEmail = async () => {
    try {
      const { data } = await verificationApi.sendEmail(user.email);
      showMessage(data.message);
    } catch (err) {
      showError(err);
    }
  };

  const verifyEmail = async () => {
    try {
      const { data } = await verificationApi.verifyEmail({ email: user.email, code: verify.emailCode });
      await reloadUser();
      showMessage(data.verified ? '이메일 인증이 완료되었습니다.' : '인증번호를 확인해주세요.');
    } catch (err) {
      showError(err);
    }
  };

  const sendPhone = async () => {
    try {
      const { data } = await verificationApi.sendPhone(verify.phone);
      showMessage(data.message);
    } catch (err) {
      showError(err);
    }
  };

  const verifyPhone = async () => {
    try {
      const { data } = await verificationApi.verifyPhone({ phone: verify.phone, code: verify.phoneCode });
      await reloadUser();
      showMessage(data.verified ? '전화번호 인증이 완료되었습니다.' : '인증번호를 확인해주세요.');
    } catch (err) {
      showError(err);
    }
  };

  return (
    <div className="animate-fadeIn">
      <header className="mb-8">
        <h1 className="text-4xl font-extrabold tracking-tight">계정</h1>
        <p className="mt-2 text-[#86868b]">
          {user.email} · 가입 {formatDateTime(user.created_at)}
        </p>
      </header>

      {(status.message || status.error) && (
        <div
          className={`mb-6 rounded-xl p-4 text-sm font-semibold ${
            status.error ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-[#0071e3]'
          }`}
        >
          {status.error || status.message}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="surface">
          <h2 className="mb-5 text-2xl font-bold">프로필</h2>
          <form onSubmit={updateProfile} className="flex flex-col gap-4">
            <label>
              <span className="mb-2 block text-sm font-semibold text-[#86868b]">닉네임</span>
              <input className="field" value={nickname} onChange={(event) => setNickname(event.target.value)} />
            </label>
            <button className="btn-primary" type="submit">
              저장
            </button>
          </form>
        </section>

        <section className="surface">
          <h2 className="mb-5 text-2xl font-bold">비밀번호</h2>
          <form onSubmit={changePassword} className="flex flex-col gap-4">
            <input
              className="field"
              type="password"
              placeholder="현재 비밀번호"
              value={passwords.current_password}
              onChange={(event) => setPasswords((prev) => ({ ...prev, current_password: event.target.value }))}
            />
            <input
              className="field"
              type="password"
              placeholder="새 비밀번호"
              value={passwords.new_password}
              onChange={(event) => setPasswords((prev) => ({ ...prev, new_password: event.target.value }))}
            />
            <button className="btn-primary" type="submit">
              변경
            </button>
          </form>
        </section>

        <section className="surface">
          <h2 className="mb-5 text-2xl font-bold">인증</h2>
          <div className="mb-6 rounded-xl bg-[#f5f5f7] p-4">
            <div className="mb-2 text-sm font-bold">이메일 인증</div>
            <div className="mb-3 text-sm text-[#86868b]">
              상태: {user.is_verified ? '인증 완료' : '미인증'}
            </div>
            <div className="flex gap-2">
              <input
                className="field py-2"
                placeholder="인증번호"
                value={verify.emailCode}
                onChange={(event) => setVerify((prev) => ({ ...prev, emailCode: event.target.value }))}
              />
              <button className="btn-secondary py-2" type="button" onClick={sendEmail}>
                발송
              </button>
              <button className="btn-primary py-2" type="button" onClick={verifyEmail}>
                확인
              </button>
            </div>
          </div>
          <div className="rounded-xl bg-[#f5f5f7] p-4">
            <div className="mb-2 text-sm font-bold">전화번호 인증</div>
            <div className="flex flex-col gap-2 md:flex-row">
              <input
                className="field py-2"
                placeholder="010-0000-0000"
                value={verify.phone}
                onChange={(event) => setVerify((prev) => ({ ...prev, phone: event.target.value }))}
              />
              <input
                className="field py-2"
                placeholder="인증번호"
                value={verify.phoneCode}
                onChange={(event) => setVerify((prev) => ({ ...prev, phoneCode: event.target.value }))}
              />
              <button className="btn-secondary py-2" type="button" onClick={sendPhone}>
                발송
              </button>
              <button className="btn-primary py-2" type="button" onClick={verifyPhone}>
                확인
              </button>
            </div>
          </div>
        </section>

        <section className="surface">
          <h2 className="mb-5 text-2xl font-bold">알림 설정</h2>
          {status.loading || !settings ? (
            <div className="text-sm text-[#86868b]">설정을 불러오는 중입니다.</div>
          ) : (
            <div className="flex flex-col gap-4">
              <label className="flex items-center justify-between rounded-xl bg-[#f5f5f7] p-4">
                <span className="font-semibold">찜 알림 사용</span>
                <input
                  type="checkbox"
                  checked={settings.watchlist_alerts_enabled}
                  onChange={(event) =>
                    setSettings((prev) => ({ ...prev, watchlist_alerts_enabled: event.target.checked }))
                  }
                />
              </label>
              <div className="grid gap-3 md:grid-cols-2">
                {['email', 'sms'].map((channel) => (
                  <label key={channel} className="flex items-center justify-between rounded-xl bg-[#f5f5f7] p-4">
                    <span className="font-semibold">{channel === 'email' ? '이메일' : 'SMS'}</span>
                    <input
                      type="checkbox"
                      checked={settings.channels[channel]}
                      onChange={(event) =>
                        setSettings((prev) => ({
                          ...prev,
                          channels: { ...prev.channels, [channel]: event.target.checked },
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
              <label className="flex items-center justify-between rounded-xl bg-[#f5f5f7] p-4">
                <span className="font-semibold">방해금지</span>
                <input
                  type="checkbox"
                  checked={settings.dnd.enabled}
                  onChange={(event) =>
                    setSettings((prev) => ({
                      ...prev,
                      dnd: { ...prev.dnd, enabled: event.target.checked },
                    }))
                  }
                />
              </label>
              <div className="grid gap-3 md:grid-cols-2">
                <input
                  className="field"
                  type="time"
                  value={settings.dnd.start}
                  onChange={(event) =>
                    setSettings((prev) => ({ ...prev, dnd: { ...prev.dnd, start: event.target.value } }))
                  }
                  disabled={!settings.dnd.enabled}
                />
                <input
                  className="field"
                  type="time"
                  value={settings.dnd.end}
                  onChange={(event) =>
                    setSettings((prev) => ({ ...prev, dnd: { ...prev.dnd, end: event.target.value } }))
                  }
                  disabled={!settings.dnd.enabled}
                />
              </div>
              <button className="btn-primary" type="button" onClick={saveSettings}>
                알림 설정 저장
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
