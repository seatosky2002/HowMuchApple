import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const navItems = [
  { to: '/', label: '검색' },
  { to: '/market', label: '시세' },
  { to: '/watchlist', label: '찜' },
  { to: '/alerts', label: '알림' },
];

export default function Layout() {
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-white text-[#1d1d1f]">
      <header className="fixed top-0 right-0 left-0 z-50 border-b border-[#d2d2d7] bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1280px] items-center justify-between px-4 py-3 md:px-8">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="text-left text-lg font-extrabold tracking-tight md:text-2xl"
          >
            How Much, Apple
          </button>
          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-full px-4 py-2 text-sm font-semibold transition ${
                    isActive ? 'bg-[#1d1d1f] text-white' : 'text-[#6e6e73] hover:bg-[#f5f5f7]'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            {isAuthenticated ? (
              <>
                <button
                  type="button"
                  onClick={() => navigate('/account')}
                  className="hidden rounded-full bg-[#f5f5f7] px-4 py-2 text-sm font-semibold text-[#1d1d1f] md:block"
                >
                  {user?.nickname || '내 계정'}
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-full border border-[#d2d2d7] px-3 py-2 text-xs font-semibold text-[#6e6e73] transition hover:border-[#1d1d1f] hover:text-[#1d1d1f] md:text-sm"
                >
                  로그아웃
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="rounded-full border border-[#0071e3] px-4 py-2 text-sm font-semibold text-[#0071e3] transition hover:bg-[#0071e3] hover:text-white"
              >
                로그인
              </button>
            )}
          </div>
        </div>
        <nav className="mx-auto flex max-w-[1280px] justify-around border-t border-[#f5f5f7] px-2 py-2 md:hidden">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-full px-3 py-1.5 text-xs font-semibold ${
                  isActive ? 'bg-[#1d1d1f] text-white' : 'text-[#6e6e73]'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-[1280px] px-4 pt-[108px] pb-12 md:px-8 md:pt-[92px]">
        <Outlet />
      </main>
    </div>
  );
}
