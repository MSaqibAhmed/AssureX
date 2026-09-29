import { lazy, Suspense, useEffect, useState } from 'react';
import { Navigate, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import Shell, { homes } from '../components/Shell';
import { Notifications, Reports, Account, Help, Auth, SystemPage } from '../pages/Shared';
import { api } from '../api/client';
import { acceptSession, actions, store } from './store';
import { ErrorMessage } from '../api/hooks';

const Dashboard = lazy(() => import('../pages/Dashboard'));
const products = () => import('../pages/Products');
const claims = () => import('../pages/Claims');
const staff = () => import('../pages/Staff');
const admin = () => import('../pages/Admin');
const screen = (loader, name) => lazy(() => loader().then((module) => ({ default: module[name] })));
const [ProductList, ProductForm, ProductDetail, WarrantyForm, DocumentForm, Receipts] = [
  'ProductList',
  'ProductForm',
  'ProductDetail',
  'WarrantyForm',
  'DocumentForm',
  'Receipts',
].map((name) => screen(products, name));
const [
  ClaimList,
  ClaimWizard,
  Processing,
  ClaimResult,
  RequestReview,
  ClaimDetail,
  InformationForm,
  ClaimReport,
] = [
  'ClaimList',
  'ClaimWizard',
  'Processing',
  'ClaimResult',
  'RequestReview',
  'ClaimDetail',
  'InformationForm',
  'ClaimReport',
].map((name) => screen(claims, name));
const [
  WorkQueue,
  ReviewWorkspace,
  RequestInformation,
  DecisionSaved,
  ServiceDetail,
  ServiceForm,
  ServiceHistory,
] = [
  'WorkQueue',
  'ReviewWorkspace',
  'RequestInformation',
  'DecisionSaved',
  'ServiceDetail',
  'ServiceForm',
  'ServiceHistory',
].map((name) => screen(staff, name));
const [
  Policies,
  PolicyEditor,
  Models,
  ModelDetail,
  ModelActivation,
  People,
  PersonForm,
  Assignments,
  Audit,
] = [
  'Policies',
  'PolicyEditor',
  'Models',
  'ModelDetail',
  'ModelActivation',
  'People',
  'PersonForm',
  'Assignments',
  'Audit',
].map((name) => screen(admin, name));
function LoadingScreen() {
  return (
    <div className="loading-screen" role="status" aria-label="Loading page">
      <div className="skeleton-title" />
      <div className="skeleton-grid">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} />
        ))}
      </div>
      <div className="skeleton-panel" />
      <span className="sr-only">Loading your workspace…</span>
    </div>
  );
}

function AuthGuard() {
  return useSelector((s) => s.app.session.authenticated) ? (
    <Shell />
  ) : (
    <Navigate to="/sign-in" replace />
  );
}
function RoleGuard({ role }) {
  return useSelector((s) => s.app.session.role) === role ? <Outlet /> : <SystemPage denied />;
}
function Home() {
  return <Navigate to={homes[useSelector((s) => s.app.session.role)]} replace />;
}

export default function App() {
  const navigate = useNavigate();
  const ready = useSelector((s) => s.app.session.ready);
  const [bootError, setBootError] = useState(null);
  useEffect(() => {
    let active = true;
    api
      .get('/me', { skipAuthEvent: true })
      .then((data) => {
        if (active) acceptSession(data);
      })
      .catch((error) => {
        if (!active) return;
        if (error.status === 401) store.dispatch(actions.signedOut());
        else setBootError(error);
      });
    const auth = (event) => {
      if (event.detail === 401) {
        store.dispatch(actions.signedOut());
        navigate('/sign-in', { replace: true });
      } else navigate('/access-denied', { replace: true });
    };
    window.addEventListener('api-auth', auth);
    return () => {
      active = false;
      window.removeEventListener('api-auth', auth);
    };
  }, [navigate]);
  if (bootError)
    return (
      <main>
        <ErrorMessage error={bootError} />
        <button onClick={() => window.location.reload()}>Retry connection</button>
      </main>
    );
  if (!ready) return <LoadingScreen />;
  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        <Route path="sign-in" element={<Auth key="sign-in" />} />
        <Route path="register" element={<Auth key="register" mode="register" />} />
        <Route element={<AuthGuard />}>
          <Route index element={<Home />} />
          <Route element={<RoleGuard role="customer" />}>
            <Route path="overview" element={<Dashboard />} />
            <Route path="products" element={<ProductList />} />
            <Route path="products/new" element={<ProductForm />} />
            <Route path="products/:id/edit" element={<ProductForm />} />
            <Route path="products/:id/warranty/edit" element={<WarrantyForm />} />
            <Route path="products/:id/documents/new" element={<DocumentForm />} />
            <Route path="products/:id/:tab?" element={<ProductDetail />} />
            <Route path="documents" element={<Receipts />} />
            <Route path="receipts" element={<Navigate to="/documents" replace />} />
            <Route path="receipts/new" element={<Navigate to="/documents" replace />} />
            <Route path="claims" element={<ClaimList />} />
            <Route path="claims/new" element={<ClaimWizard key="new" />} />
            <Route path="claims/:id/edit" element={<ClaimWizard />} />
            <Route path="claims/:id/processing" element={<Processing />} />
            <Route path="claims/:id/result" element={<ClaimResult />} />
            <Route path="claims/:id/request-review" element={<RequestReview />} />
            <Route path="claims/:id/information" element={<InformationForm />} />
            <Route path="claims/:id/evidence/new" element={<InformationForm evidenceOnly />} />
            <Route path="claims/:id/report" element={<ClaimReport />} />
            <Route path="claims/:id" element={<ClaimDetail />} />
          </Route>
          <Route element={<RoleGuard role="service" />}>
            <Route path="service" element={<Dashboard />} />
            <Route path="service/queue" element={<WorkQueue />} />
            <Route path="service/history" element={<ServiceHistory />} />
            <Route path="service/claims/new" element={<ClaimWizard key="service-new" />} />
            <Route path="service/claims/:id/edit" element={<ClaimWizard />} />
            <Route path="service/claims/:id" element={<ServiceDetail />} />
            <Route path="service/claims/:id/:type" element={<ServiceForm />} />
          </Route>
          <Route element={<RoleGuard role="reviewer" />}>
            <Route path="review/dashboard" element={<Dashboard />} />
            <Route path="review" element={<WorkQueue review />} />
            <Route path="review/:id/request-information" element={<RequestInformation />} />
            <Route path="review/:id/saved" element={<DecisionSaved />} />
            <Route path="review/:id/:tab?" element={<ReviewWorkspace />} />
          </Route>
          <Route element={<RoleGuard role="admin" />}>
            <Route path="admin" element={<Dashboard />} />
            <Route path="admin/policies" element={<Policies />} />
            <Route path="admin/policies/new" element={<PolicyEditor />} />
            <Route path="admin/policies/:id" element={<PolicyEditor />} />
            <Route path="admin/models" element={<Models />} />
            <Route path="admin/models/:id" element={<ModelDetail />} />
            <Route path="admin/models/:id/activate" element={<ModelActivation />} />
            <Route path="admin/people" element={<People />} />
            <Route path="admin/people/new" element={<PersonForm />} />
            <Route path="admin/people/:id" element={<Navigate to="/admin/people" replace />} />
            <Route path="admin/assignments" element={<Assignments />} />
            <Route path="admin/audit" element={<Audit />} />
          </Route>
          <Route path="notifications" element={<Notifications />} />
          <Route path="reports" element={<Reports />} />
          <Route path="reports/claims/:id" element={<ClaimReport />} />
          <Route path="account" element={<Account />} />
          <Route path="help" element={<Help />} />
          <Route path="access-denied" element={<SystemPage denied />} />
          <Route path="*" element={<SystemPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
