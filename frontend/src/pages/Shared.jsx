import { useState } from 'react';
import { useSelector } from 'react-redux';
import { Link, useNavigate } from 'react-router-dom';
import { ShieldCheck, ArrowRight, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';
import { acceptSession, actions, store } from '../app/store';
import { useResource, ResourceState, ErrorMessage, Unavailable, Pagination } from '../api/hooks';
import { Logo, homes } from '../components/Shell';
import { Banner, Button, Card, Input, PageHeader } from '../components/ui';
import { ClaimList } from './Claims';

export function Auth({ mode = 'sign-in', unavailable = false }) {
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    if (unavailable) return;
    setBusy(true);
    setError(null);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const data = await api.post(mode === 'register' ? '/auth/register' : '/auth/login', values, {
        skipAuthEvent: true,
      });
      acceptSession(data);
      navigate(homes[data.user.role], { replace: true });
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <section className="auth-brand">
        <Link to="/sign-in">
          <Logo />
        </Link>
        <div className="auth-brand-content">
          <span className="tiny-pill">INTELLIGENT CLAIM VALIDATION</span>
          <h1>
            Clear evidence.
            <br />
            Confident
            <br />
            <span>decisions.</span>
          </h1>
          <p>
            One secure workspace for warranty claims, independent AI analysis and traceable human
            review.
          </p>
          <div className="auth-brand-cards">
            <div>
              <ShieldCheck size={27} />
              <strong>Evidence first.</strong>
              <span>Products, documents and coverage.</span>
            </div>
            <div>
              <CheckCircle2 size={27} />
              <strong>Human oversight.</strong>
              <span>Every decision has a reason.</span>
            </div>
          </div>
        </div>
        <span className="small">Made for the things that matter.</span>
      </section>
      <main className="auth-form-side">
        <div className="auth-top-link">
          <Link to={mode === 'sign-in' ? '/register' : '/sign-in'}>
            {mode === 'sign-in' ? 'Create an account' : 'Sign in'} <ArrowRight size={15} />
          </Link>
        </div>
        <div className="auth-form">
          <span className="auth-icon">
            <span className="brand-mark">
              <img src="/brand/assurex-mark.png?v=transparent-1" alt="" />
            </span>
          </span>
          <span className="eyebrow">WELCOME TO ASSUREX</span>
          <h1>{mode === 'register' ? 'Create your workspace.' : 'Welcome back.'}</h1>
          <p>Sign in to manage your products, evidence and claims.</p>
          {unavailable && (
            <div role="status" className="auth-demo-note">
              Sign-in is temporarily unavailable. Please try again later.
              <button type="button" onClick={() => window.location.reload()}>
                Retry connection
              </button>
            </div>
          )}
          {['sign-in', 'register'].includes(mode) ? (
            <form onSubmit={submit}>
              {mode === 'register' && (
                <Input label="Full name" name="name" required maxLength={100} autoComplete="name" />
              )}
              <Input
                label="Email address"
                name="email"
                type="email"
                required
                autoComplete="email"
              />
              <Input
                label="Password"
                name="password"
                type="password"
                minLength={8}
                maxLength={128}
                required
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
              <ErrorMessage error={error} />
              <Button type="submit" disabled={busy || unavailable} className="full-width">
                {busy ? 'Connecting…' : mode === 'register' ? 'Create account' : 'Login'}
                <ArrowRight size={17} />
              </Button>
              <p className="auth-demo-note">
                Secure server session · Passwords are never stored in this browser.
              </p>
            </form>
          ) : (
            <Unavailable title="Password recovery">
              Password reset/email delivery is not implemented by the backend. Contact your
              administrator; no reset email has been sent.
            </Unavailable>
          )}
        </div>
        <span className="auth-copyright">© 2026 AssureX · Thoughtfully simple.</span>
      </main>
    </div>
  );
}
export function Notifications() {
  const [page, setPage] = useState(1);
  const [error, setError] = useState(null);
  const resource = useResource(`/notifications?page=${page}`);
  async function mark(id) {
    try {
      await api.patch(`/notifications/${id}`, { read: true });
      resource.reload();
    } catch (error) {
      setError(error);
    }
  }
  return (
    <>
      <PageHeader title="Your updates" description="Notifications from your server workspace." />
      <ErrorMessage error={error} />
      <ResourceState resource={resource}>
        <Card className="notification-list">
          {resource.data?.items.map((n) => (
            <div className={`notice ${n.read ? '' : 'unread'}`} key={n.id}>
              <div>
                <strong>{n.event_type}</strong>
                <p>{n.claim_id}</p>
                <Link to={`/reports/claims/${n.claim_id}`}>View claim</Link>
              </div>
              {!n.read && <Button onClick={() => mark(n.id)}>Mark read</Button>}
            </div>
          ))}
          {resource.data?.total === 0 && <p>No notifications yet.</p>}
        </Card>
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
    </>
  );
}
export function Reports() {
  return <ClaimList title="Claims report" />;
}
export function Account() {
  const user = useSelector((s) => s.app.session.user);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const updated = await api.patch('/me', Object.fromEntries(new FormData(event.currentTarget)));
      store.dispatch(actions.signedIn(updated));
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader title="Your account" />
      <Card title="Personal details">
        <p>{user.email_normalized}</p>
        <p>{user.role}</p>
        <form onSubmit={save}>
          <Input label="Full name" name="name" defaultValue={user.name} required maxLength={100} />
          <Input label="Phone" name="phone" defaultValue={user.phone || ''} maxLength={40} />
          <ErrorMessage error={error} />
          <Button disabled={busy}>Save profile</Button>
        </form>
      </Card>
    </>
  );
}
export function Help() {
  return (
    <>
      <PageHeader title="How can we help?" />
      <Card title="Your claim, step by step">
        <p>
          Register a product, record its existing warranty coverage, create a claim, upload receipt
          and serial evidence, and verify extracted OCR fields before submitting.
        </p>
        <p>
          Processing status comes from the worker. Model recommendations are advisory; a reviewer
          records the final decision.
        </p>
        <p>
          Evidence accepts PDF, JPEG or PNG up to 10 MiB. PDFs may have at most 10 pages. Files are
          stored privately on the server.
        </p>
        <Banner>
          AssureX validates claims; it does not issue warranties or connect to live manufacturer or
          payment systems. Summary cards contain claim information only, never another model’s
          predictions.
        </Banner>
      </Card>
    </>
  );
}
export function SystemPage({ denied = false }) {
  return (
    <div className="result-page">
      <Card className="result-card">
        <h1>{denied ? 'Access restricted.' : 'This page isn’t here.'}</h1>
        <p>
          {denied
            ? 'Your server session does not have access to this resource.'
            : 'Check the address or return to your workspace.'}
        </p>
        <Button to="/">Back to your workspace</Button>
      </Card>
    </div>
  );
}
