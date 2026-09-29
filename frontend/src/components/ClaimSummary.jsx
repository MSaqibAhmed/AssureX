import { CalendarDays, ShieldCheck, Wrench, FileText, Activity } from 'lucide-react';
import { Logo } from './Shell';
import { useResource } from '../api/hooks';
import { faultOptions } from '../pages/claimOptions';

const documentLabels = {
  receipt: 'Invoice',
  warranty: 'Warranty',
  serial_photo: 'Serial photo',
  diagnostic: 'Diagnostic report',
  supporting: 'Supporting document',
  fault_image: 'Fault image',
  fault_video: 'Fault video',
};
const readable = (value) => value?.replaceAll('_', ' ') || 'Not provided';
const date = (value) => (value ? new Date(`${value.slice(0, 10)}T00:00:00`) : null);
const formatDate = (value) =>
  date(value)?.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

function productAge(purchase) {
  const start = date(purchase);
  const today = new Date();
  if (!start || Number.isNaN(start.getTime()) || start > today) return 'Not available';
  const months =
    (today.getFullYear() - start.getFullYear()) * 12 +
    today.getMonth() -
    start.getMonth() -
    (today.getDate() < start.getDate() ? 1 : 0);
  if (months < 1) return 'Under 1 month';
  const years = Math.floor(months / 12);
  const remainder = months % 12;
  return [
    years && `${years} ${years === 1 ? 'year' : 'years'}`,
    remainder && `${remainder} ${remainder === 1 ? 'month' : 'months'}`,
  ]
    .filter(Boolean)
    .join(' ');
}

export default function ClaimSummary({ claim, workflow }) {
  const documents = useResource(`/claims/${claim.id}/documents`);
  const history = useResource(`/products/${claim.product_id}/service-history`);
  const product = workflow.data?.product;
  const warranty = workflow.data?.warranty;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = date(warranty?.start_date);
  const end = date(warranty?.expiry_date);
  const coverage = workflow.loading
    ? 'Loading…'
    : workflow.error
      ? 'Unavailable'
      : !warranty
        ? 'Not recorded'
        : !start || !end || Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())
          ? 'Dates unavailable'
          : today < start
            ? 'Starts soon'
            : today > end
              ? 'Expired'
              : 'Active';
  const repairs = history.data?.filter((record) => record.kind === 'repair');
  const types = [...new Set((documents.data || []).map((document) => document.type))];
  const fault =
    faultOptions.find((option) => option.value && option.value === claim.facts?.fault_category)
      ?.label || readable(claim.facts?.fault_category);
  const retries = [workflow, history, documents].filter((resource) => resource.error);
  return (
    <section className="claim-summary" aria-label="Claim summary">
      <div className="claim-summary-brand">
        <Logo />
        <div>
          <span className="summary-kicker">CLAIM AT A GLANCE</span>
          <h2>Claim summary</h2>
        </div>
        <p>
          {product
            ? `${product.brand} ${product.model}`
            : workflow.loading
              ? 'Loading product…'
              : 'Product details unavailable'}
        </p>
        <span className="summary-reference">{claim.public_claim_id}</span>
      </div>
      <div className="claim-summary-content">
        <dl className="summary-metrics">
          <div>
            <dt>
              <CalendarDays size={16} aria-hidden="true" />
              Product Age
            </dt>
            <dd>{workflow.loading ? 'Loading…' : productAge(product?.purchase_date)}</dd>
            <small>
              {product?.purchase_date
                ? `Purchased ${formatDate(product.purchase_date)}`
                : 'Purchase date not available'}
            </small>
          </div>
          <div>
            <dt>
              <ShieldCheck size={16} aria-hidden="true" />
              Warranty
            </dt>
            <dd className={coverage === 'Expired' ? 'summary-expired' : ''}>{coverage}</dd>
            <small>
              {warranty?.expiry_date
                ? `Coverage ends ${formatDate(warranty.expiry_date)}`
                : 'Provider coverage'}
            </small>
          </div>
          <div>
            <dt>
              <Activity size={16} aria-hidden="true" />
              Fault Type
            </dt>
            <dd className="summary-text-value">{fault}</dd>
            <small>
              {claim.facts?.fault_date
                ? `Reported issue date ${formatDate(claim.facts.fault_date)}`
                : 'Issue date not provided'}
            </small>
          </div>
          <div>
            <dt>
              <Wrench size={16} aria-hidden="true" />
              Repair History
            </dt>
            <dd>
              {history.loading
                ? 'Loading…'
                : history.error
                  ? 'Unavailable'
                  : `${repairs?.length ?? 0} ${(repairs?.length ?? 0) === 1 ? 'repair' : 'repairs'}`}
            </dd>
            <small>
              {history.error
                ? 'Could not load service records'
                : repairs?.length
                  ? `Latest ${formatDate(repairs[0].date)}`
                  : 'Recorded service history'}
            </small>
          </div>
        </dl>
        <div className="summary-documents">
          <h3>
            <FileText size={16} aria-hidden="true" />
            Documents
          </h3>
          <div className="summary-document-tags">
            {documents.loading ? (
              <span>Loading documents…</span>
            ) : documents.error ? (
              <span>Documents unavailable</span>
            ) : types.length ? (
              types.map((type) => (
                <span className="summary-document-tag" key={type}>
                  {documentLabels[type] || readable(type)}
                </span>
              ))
            ) : (
              <span>No documents added yet</span>
            )}
          </div>
        </div>
        {retries.length > 0 && (
          <button
            className="summary-retry"
            onClick={() => retries.forEach((resource) => resource.reload())}
          >
            Some details could not load. Retry
          </button>
        )}
      </div>
    </section>
  );
}
