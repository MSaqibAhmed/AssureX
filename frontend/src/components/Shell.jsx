import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { Bell, CircleHelp, ChevronDown, Menu, X, LogOut, UserRound, Search } from 'lucide-react';
import { actions, logout } from '../app/store';
import { useResource } from '../api/hooks';
import { notifyError } from './notifications';
import { toast as showToast } from 'react-toastify';
const roles = {
  customer: 'Customer',
  service: 'Service',
  reviewer: 'Reviewer',
  admin: 'Administrator',
};

export const homes = {
  customer: '/overview',
  service: '/service',
  reviewer: '/review',
  admin: '/admin',
};
const navigation = {
  customer: [
    ['Overview', '/overview'],
    ['Products', '/products'],
    ['Claims', '/claims'],
    ['Documents', '/documents'],
  ],
  service: [
    ['Overview', '/service'],
    ['Work Queue', '/service/queue'],
    ['Service History', '/service/history'],
    ['Reports', '/reports'],
  ],
  reviewer: [
    ['Dashboard', '/review/dashboard'],
    ['Review Queue', '/review'],
    ['Reports', '/reports'],
  ],
  admin: [
    ['Overview', '/admin'],
    ['Policies', '/admin/policies'],
    ['Models', '/admin/models'],
    ['People', '/admin/people'],
    ['Assignments', '/admin/assignments'],
    ['Audit', '/admin/audit'],
    ['Reports', '/reports'],
  ],
};
export function Logo() {
  return (
    <span className="logo brand-logo">
      <img src="/brand/assurex-logo.png?v=transparent-1" alt="AssureX" width="1774" height="887" />
    </span>
  );
}
export default function Shell() {
  const data = useSelector((s) => s.app);
  const { session, toast } = data;
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const [menu, setMenu] = useState(false);
  const [profile, setProfile] = useState(false);
  const notices = useResource('/notifications?limit=100');
  const unread = notices.data?.unread_count ?? 0;
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    if (toast) {
      showToast.info(toast, { toastId: toast });
      dispatch(actions.toast(null));
    }
  }, [toast, dispatch]);
  const closeMenus = () => {
    setMenu(false);
    setProfile(false);
  };
  return (
    <>
      {data.storageError && (
        <p className="banner error" role="alert">
          {data.storageError}
        </p>
      )}
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <div className="nav-inner">
          <Link to={homes[session.role]} onClick={closeMenus} aria-label="AssureX home">
            <Logo />
          </Link>
          <nav className={`main-nav ${menu ? 'open' : ''}`} aria-label="Main navigation">
            {navigation[session.role].map(([name, path]) => (
              <NavLink key={path} to={path} end={path === homes[session.role]} onClick={closeMenus}>
                {name}
              </NavLink>
            ))}
            <Link className="mobile-only" to="/notifications" onClick={closeMenus}>
              Notifications
            </Link>
            <Link className="mobile-only" to="/account" onClick={closeMenus}>
              Account
            </Link>
            <Link className="mobile-only" to="/help" onClick={closeMenus}>
              Help
            </Link>
          </nav>
          <div className="nav-right">
            <Link
              to={
                session.role === 'customer'
                  ? '/claims'
                  : session.role === 'service'
                    ? '/service/queue'
                    : homes[session.role]
              }
              className="icon-button nav-search"
              aria-label="Search"
            >
              <Search size={19} />
            </Link>
            <Link to="/help" className="icon-button nav-help" aria-label="Help center">
              <CircleHelp size={20} />
            </Link>
            <Link
              to="/notifications"
              className="icon-button notification-button"
              aria-label={`Notifications, ${unread} unread`}
            >
              <Bell size={20} />
              {unread > 0 && <span className="notification-dot" />}
            </Link>
            <span className="nav-divider" />
            <div className="profile-wrap">
              <button
                className="profile-trigger"
                aria-label="Open profile menu"
                aria-expanded={profile}
                onClick={() => setProfile(!profile)}
              >
                <span className="avatar">{session.user.initials}</span>
                <ChevronDown size={15} />
              </button>
              {profile && (
                <div className="profile-menu">
                  <strong>{session.user.name}</strong>
                  <small>{roles[session.role]}</small>
                  <Link to="/account" onClick={closeMenus}>
                    <UserRound size={16} />
                    Account settings
                  </Link>
                  <button
                    onClick={async () => {
                      try {
                        await logout();
                        navigate('/sign-in');
                      } catch (error) {
                        notifyError(error);
                      }
                    }}
                  >
                    <LogOut size={16} />
                    Sign out
                  </button>
                </div>
              )}
            </div>
            <button
              className="icon-button mobile-only"
              aria-label="Toggle navigation"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X size={23} /> : <Menu size={23} />}
            </button>
          </div>
        </div>
      </header>
      <div className="app-body">
        <div className="context-bar">
          <div>
            <span className="context-dot" /> Claim input → Independent analysis → Traceable
            decisions
          </div>
        </div>
        <main id="main-content">
          <Outlet />
        </main>
        <footer className="footer">
          <span>© 2026 AssureX · Warranty claim intelligence</span>
          <div>
            <span className="context-dot" /> Connected workspace
            <span className="footer-separator">/</span>
            <Link to="/help">Need a hand?</Link>
          </div>
        </footer>
      </div>
    </>
  );
}
