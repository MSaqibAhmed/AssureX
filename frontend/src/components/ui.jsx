import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowDownUp,
  X,
  Check,
  AlertCircle,
  Inbox,
} from 'lucide-react';

export function Button({
  to,
  children,
  variant = 'primary',
  className = '',
  icon: Icon,
  ...props
}) {
  const cls = `button ${variant} ${className}`;
  return to ? (
    <Link to={to} className={cls} {...props}>
      {Icon && <Icon size={17} />}
      {children}
    </Link>
  ) : (
    <button className={cls} {...props}>
      {Icon && <Icon size={17} />}
      {children}
    </button>
  );
}
export function PageHeader({ eyebrow, title, description, children, back }) {
  return (
    <header className="page-header">
      <div>
        {back && (
          <Link className="back-link" to={back}>
            <ArrowLeft size={15} /> Back
          </Link>
        )}
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children && <div className="header-actions">{children}</div>}
    </header>
  );
}
export function Card({ children, className = '', title, subtitle, action }) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="card-heading">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Badge({ status }) {
  const kind = ['Approved', 'active', 'completed', 'PASS', 'Likely Valid', 'Strong Match'].includes(status)
    ? 'green'
    : ['Rejected', 'failed', 'FAIL', 'Likely Invalid', 'expired'].includes(status)
      ? 'red'
      : [
            'Manual Review',
            'Additional Information Required',
            'Under Evaluation',
            'near-expiry',
            'Manual Review Required',
            'Waiting',
            'Candidate',
            'In progress',
            'Needs review',
          ].includes(status)
        ? 'orange'
        : 'neutral';
  return (
    <span className={`badge ${kind}`}>
      <span className="status-dot" />
      {status}
    </span>
  );
}
export function Field({ label, error, help, children, required, className = '' }) {
  const id = useId();
  return (
    <div className={`field ${error ? 'has-error' : ''} ${className}`}>
      <label id={id}>
        {label}
        {required && (
          <span className="required" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>
      {children}
      <span className={error ? 'field-error' : 'field-help'} role={error ? 'alert' : undefined}>
        {error || help}
      </span>
    </div>
  );
}
export function Input({ label, error, help, required, ...props }) {
  const id = useId();
  return (
    <div className={`field ${error ? 'has-error' : ''}`}>
      <label htmlFor={id}>
        {label}
        {required && (
          <span className="required" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>
      <input
        id={id}
        aria-label={label}
        aria-invalid={!!error}
        aria-describedby={error || help ? `${id}-help` : undefined}
        required={required}
        {...props}
      />
      {(help || error) && (
        <span
          id={`${id}-help`}
          className={error ? 'field-error' : 'field-help'}
          role={error ? 'alert' : undefined}
        >
          {error || help}
        </span>
      )}
    </div>
  );
}
export function Select({ label, options, error, help, required, ...props }) {
  const id = useId();
  return (
    <div className={`field ${error ? 'has-error' : ''}`}>
      <label htmlFor={id}>
        {label}
        {required && (
          <span className="required" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>
      <select id={id} aria-label={label} required={required} aria-invalid={!!error} {...props}>
        {options.map((o) => (
          <option
            key={typeof o === 'string' ? o : o.value}
            value={typeof o === 'string' ? o : o.value}
          >
            {typeof o === 'string' ? o : o.label}
          </option>
        ))}
      </select>
      {(help || error) && (
        <span className={error ? 'field-error' : 'field-help'}>{error || help}</span>
      )}
    </div>
  );
}
export function Textarea({ label, error, required, help, ...props }) {
  const id = useId();
  return (
    <div className={`field ${error ? 'has-error' : ''}`}>
      <label htmlFor={id}>
        {label}
        {required && (
          <span className="required" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>
      <textarea id={id} rows={4} required={required} aria-invalid={!!error} {...props} />
      {(help || error) && (
        <span className={error ? 'field-error' : 'field-help'}>{error || help}</span>
      )}
    </div>
  );
}
export function Empty({
  title = 'Nothing here just yet',
  description = 'Your records will appear here.',
  action,
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Inbox size={28} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function Banner({ children, tone = 'info' }) {
  return (
    <div className={`banner ${tone}`}>
      <AlertCircle size={18} />
      <div>{children}</div>
    </div>
  );
}
export function Tabs({ items }) {
  return (
    <nav className="tabs" aria-label="Page sections">
      {items.map((t) => (
        <Link key={t.label} className={t.active ? 'active' : ''} to={t.to}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
export function KeyValues({ items }) {
  return (
    <dl className="key-values">
      {items.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v === '' || v == null ? 'Not provided' : v}</dd>
        </div>
      ))}
    </dl>
  );
}
export function Table({
  columns,
  rows,
  searchKeys,
  filters = [],
  filterKey = 'status',
  initialFilter = 'All',
  emptyTitle,
  action,
  pageSize = 6,
}) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState(initialFilter);
  const [page, setPage] = useState(1);
  const [ascending, setAscending] = useState(false);
  const filtered = rows.filter(
    (r) =>
      (filter === 'All' ||
        r[filterKey] === filter ||
        (filter === 'Needs attention' && ['Invalid', 'Manual Review'].includes(r.status))) &&
      (searchKeys || columns.map((c) => c.key)).some((k) =>
        String(r[k] ?? '')
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
  );
  const sorted = [...filtered].sort(
    (a, b) =>
      String(a[columns[0].key]).localeCompare(String(b[columns[0].key])) * (ascending ? 1 : -1),
  );
  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const current = Math.min(page, pages);
  return (
    <div className="table-wrap">
      <div className="table-toolbar">
        <div className="search-box">
          <Search size={17} />
          <input
            aria-label="Search records"
            placeholder="Search anything..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div className="table-tools">
          {filters.length > 0 && (
            <select
              aria-label="Filter records"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                setPage(1);
              }}
            >
              <option>All</option>
              {filters.map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          )}
          <button
            className="icon-button bordered"
            onClick={() => setAscending(!ascending)}
            aria-label={`Sort ${ascending ? 'descending' : 'ascending'}`}
            title="Change sort order"
          >
            <ArrowDownUp size={17} />
          </button>
          {action}
        </div>
      </div>
      {!sorted.length ? (
        <Empty
          title={query || filter !== 'All' ? 'No matching records' : emptyTitle}
          description={
            query || filter !== 'All'
              ? 'Try another search or clear your filters.'
              : 'Add your first record to get started.'
          }
          action={
            (query || filter !== 'All') && (
              <Button
                variant="secondary"
                onClick={() => {
                  setQuery('');
                  setFilter('All');
                }}
              >
                Clear filters
              </Button>
            )
          }
        />
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c.key}>
                      {c.label}
                      {c.key === columns[0].key && (
                        <span className="sort-hint"> {ascending ? '↑' : '↓'}</span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.slice((current - 1) * pageSize, current * pageSize).map((r, i) => (
                  <tr key={r.id || i}>
                    {columns.map((c) => (
                      <td key={c.key} data-label={c.label}>
                        {c.render ? c.render(r) : r[c.key]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <span>
              Showing {(current - 1) * pageSize + 1}–{Math.min(current * pageSize, sorted.length)}{' '}
              of {sorted.length}
            </span>
            <div>
              <button
                className="icon-button"
                disabled={current === 1}
                aria-label="Previous page"
                onClick={() => setPage(current - 1)}
              >
                <ChevronLeft size={17} />
              </button>
              <span>
                {current} / {pages}
              </span>
              <button
                className="icon-button"
                disabled={current === pages}
                aria-label="Next page"
                onClick={() => setPage(current + 1)}
              >
                <ChevronRight size={17} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
export function Dialog({
  title,
  children,
  onClose,
  onConfirm,
  confirmLabel = 'Confirm',
  danger = false,
}) {
  const ref = useRef(null);
  const id = useId();
  useEffect(() => {
    const node = ref.current;
    node.showModal();
    return () => node.close();
  }, []);
  return (
    <dialog ref={ref} aria-labelledby={id} className="dialog" onCancel={onClose}>
      <div className="dialog-heading">
        <h2 id={id}>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Close dialog">
          <X size={20} />
        </button>
      </div>
      <div className="dialog-content">{children}</div>
      <div className="dialog-actions">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
export function Timeline({ items }) {
  return (
    <ol className="timeline">
      {[...items].reverse().map((h, i) => (
        <li key={i}>
          <span className="timeline-dot">
            <Check size={12} />
          </span>
          <div>
            <div className="timeline-title">
              <strong>{h.state}</strong>
              <span>Revision {h.revision}</span>
            </div>
            <p>{h.reason}</p>
            <small>
              {h.actor || 'System'} ·{' '}
              {new Date(h.date).toLocaleString('en-GB', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
              })}
              {h.visibility === 'staff' ? ' · Staff only' : ''}
            </small>
          </div>
        </li>
      ))}
    </ol>
  );
}
export function TextLink({ to, children, arrow = true }) {
  return (
    <Link className="text-link" to={to}>
      {children}
      {arrow && <ArrowUpRight size={15} />}
    </Link>
  );
}
export function FormActions({ back, children, label = 'Save changes' }) {
  return (
    <div className="form-actions">
      <Button variant="secondary" to={back}>
        Cancel
      </Button>
      <div>
        {children}
        <Button type="submit">
          {label}
          <ArrowRight size={16} />
        </Button>
      </div>
    </div>
  );
}
