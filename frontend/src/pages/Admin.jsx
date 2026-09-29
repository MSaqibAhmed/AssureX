import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ErrorMessage, useResource, ResourceState, Pagination } from '../api/hooks';
import { Button, Card, Input, PageHeader, Select, Textarea } from '../components/ui';
export function Policies() {
  const [page, setPage] = useState(1);
  const resource = useResource(`/policies?page=${page}`);
  return (
    <>
      <PageHeader title="Policies">
        <Button to="/admin/policies/new">Create policy version</Button>
      </PageHeader>
      <ResourceState resource={resource}>
        <Card>
          {resource.data?.items.map((p) => (
            <div className="list-row" key={p.id}>
              <Link to={`/admin/policies/${p.id}`}>
                {p.category} · {p.version}
              </Link>
              <span>{p.policy.coverage_months} months</span>
            </div>
          ))}
        </Card>
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
    </>
  );
}
export function PolicyEditor() {
  const { id } = useParams();
  const policy = useResource(id ? `/policies/${id}` : null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    for (const key of ['coverage_months', 'reporting_days', 'grace_days', 'reminder_window'])
      values[key] = Number(values[key]);
    for (const key of ['excluded_damage', 'required_documents', 'covered_fault_categories'])
      values[key] = values[key]
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    values.require_authorized_repairs = values.require_authorized_repairs === 'true';
    setBusy(true);
    setError(null);
    try {
      await api.post('/admin/policies', values);
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  if (id)
    return (
      <>
        <PageHeader title="Policy version">
          <Button to="/admin/policies/new">Create new version</Button>
        </PageHeader>
        <ResourceState resource={policy}>
          <Card>
            <p>
              Existing versions are immutable; previously submitted claims retain their pinned
              policy.
            </p>
            {Object.entries(policy.data?.policy || {}).map(([key, value]) => (
              <p key={key}>
                <strong>{key.replaceAll('_', ' ')}:</strong>{' '}
                {Array.isArray(value) ? value.join(', ') || 'None' : String(value)}
              </p>
            ))}
          </Card>
        </ResourceState>
      </>
    );
  return (
    <>
      <PageHeader title="Create policy version" />
      <Card>
        <form onSubmit={save}>
          <div className="form-grid">
            <Select
              label="Category"
              name="category"
              options={['mobile', 'electronics', 'appliances']}
            />
            <Input label="Version" name="version" required />
            {[
              ['Coverage months', 'coverage_months', 1, 120],
              ['Reporting days', 'reporting_days', 0, 365],
              ['Grace days', 'grace_days', 0, 90],
              ['Reminder window', 'reminder_window', 0, 365],
            ].map(([label, name, min, max]) => (
              <Input
                key={name}
                label={label}
                name={name}
                type="number"
                min={min}
                max={max}
                required
              />
            ))}
          </div>
          {[
            ['Excluded damage', 'excluded_damage'],
            ['Required document types', 'required_documents'],
            ['Covered fault categories', 'covered_fault_categories'],
          ].map(([label, name]) => (
            <Input
              key={name}
              label={label}
              name={name}
              help="Comma-separated values. Document types: receipt, serial_photo, warranty, diagnostic, supporting."
            />
          ))}
          <Select
            label="Require authorized repairs"
            name="require_authorized_repairs"
            options={[
              { value: 'true', label: 'Yes' },
              { value: 'false', label: 'No' },
            ]}
          />
          <ErrorMessage error={error} />
          <Button disabled={busy}>Create policy</Button>
        </form>
      </Card>
    </>
  );
}
export function Models() {
  const resource = useResource('/admin/models');
  return (
    <>
      <PageHeader
        title="Model registry"
        description="Independent structured-data and claim-summary-image models."
      />
      <ResourceState resource={resource}>
        <Card>
          {resource.data?.items.map((m) => (
            <div className="list-row" key={m.id}>
              <Link to={`/admin/models/${m.id}`}>
                {m.family} · {m.id}
              </Link>
              <span>{resource.data.active_ids.includes(m.id) ? 'Active' : 'Available'}</span>
            </div>
          ))}
        </Card>
      </ResourceState>
    </>
  );
}
export function ModelDetail() {
  const { id } = useParams();
  const resource = useResource('/admin/models');
  const model = resource.data?.items.find((m) => m.id === id);
  return (
    <>
      <PageHeader title="Model details" back="/admin/models" />
      <ResourceState resource={resource}>
        <Card>
          {model ? (
            <>
              <p>
                {model.family} · {model.id}
              </p>
              <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(model, null, 2)}</pre>
              <Button to={`/admin/models/${id}/activate`}>Activate this version</Button>
            </>
          ) : (
            <p>Model not found.</p>
          )}
        </Card>
      </ResourceState>
    </>
  );
}
export function ModelActivation() {
  const { id } = useParams();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true);
    setError(null);
    try {
      await api.post('/admin/model-activations', values);
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Activate model version">
      <form onSubmit={save}>
        <Input label="Model version ID" name="model_version_id" defaultValue={id || ''} required />
        <Textarea label="Activation reason" name="reason" required />
        <label className="checkbox-row">
          <input type="checkbox" required />I confirm this changes the active model for future
          evaluations.
        </label>
        <ErrorMessage error={error} />
        <Button disabled={busy}>Activate model</Button>
      </form>
    </Card>
  );
}
export function People() {
  const [page, setPage] = useState(1);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const resource = useResource(`/admin/users?page=${page}`);
  async function toggle(user) {
    setBusy(user.id);
    setError(null);
    try {
      await api.patch(`/admin/users/${user.id}`, { active: !user.active });
      resource.reload();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(null);
    }
  }
  return (
    <>
      <PageHeader title="People">
        <Button to="/admin/people/new">Create account</Button>
      </PageHeader>
      <ErrorMessage error={error} />
      <ResourceState resource={resource}>
        <Card>
          {resource.data?.items.map((u) => (
            <div className="list-row" key={u.id}>
              <div>
                <strong>{u.name}</strong>
                <p>
                  {u.email_normalized} · {u.role} · {u.active ? 'Active' : 'Disabled'}
                </p>
              </div>
              {u.role !== 'admin' && (
                <Button variant="secondary" disabled={busy === u.id} onClick={() => toggle(u)}>
                  {u.active ? 'Disable access' : 'Enable access'}
                </Button>
              )}
            </div>
          ))}
        </Card>
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
    </>
  );
}
export function PersonForm() {
  const [role, setRole] = useState('customer');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const centers = useResource('/admin/service-centers');
  async function save(event) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    setError(null);
    try {
      const values = Object.fromEntries(new FormData(form));
      if (!values.center_id) values.center_id = null;
      await api.post('/admin/users', values);
      form.reset();
      setRole('customer');
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader title="Create account" back="/admin/people" />
      <Card>
        <form onSubmit={save}>
          <Input label="Full name" name="name" required maxLength={100} />
          <Input label="Email" name="email" type="email" required />
          <Input
            label="Initial password"
            name="password"
            type="password"
            minLength={8}
            maxLength={128}
            required
            autoComplete="new-password"
          />
          <Select
            label="Role"
            name="role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            options={['customer', 'service', 'reviewer', 'admin']}
          />
          {role === 'service' && (
            <ResourceState resource={centers}>
              <Select
                label="Service center"
                name="center_id"
                required
                options={[
                  { value: '', label: 'Select service center' },
                  ...(centers.data || []).map((c) => ({ value: c.id, label: c.name || c.id })),
                ]}
              />
            </ResourceState>
          )}
          <ErrorMessage error={error} />
          <Button
            disabled={busy || (role === 'service' && (centers.loading || Boolean(centers.error)))}
          >
            Create account
          </Button>
        </form>
      </Card>
    </>
  );
}
export function Assignments() {
  const [page, setPage] = useState(1);
  const resource = useResource(`/reports?page=${page}`);
  return (
    <>
      <PageHeader
        title="Reviewer assignments"
        description="Claims are initially routed automatically. Reassignment preserves the claim history."
      />
      <ResourceState resource={resource}>
        {resource.data?.items
          .filter((c) => !['Approved', 'Rejected', 'Closed'].includes(c.status))
          .map((c) => (
            <AssignmentRow key={`${c.id}-${c.version}`} claim={c} refresh={resource.reload} />
          ))}
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
    </>
  );
}
function AssignmentRow({ claim, refresh }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const users = useResource(`/admin/users?page=${page}`);
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/claims/${claim.id}/assignment`, {
        version: claim.version,
        status: claim.status,
        reviewer_id: new FormData(event.currentTarget).get('reviewer_id'),
      });
      refresh();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title={claim.public_claim_id}>
      <p>
        Current reviewer: {claim.assigned_reviewer_id || 'Unassigned'} · {claim.status}
      </p>
      <form onSubmit={save}>
        <ResourceState resource={users}>
          <Select
            label="Assign reviewer"
            name="reviewer_id"
            required
            options={[
              { value: '', label: 'Select active reviewer' },
              ...(users.data?.items || [])
                .filter((u) => u.role === 'reviewer' && u.active)
                .map((u) => ({ value: u.id, label: `${u.name} · ${u.email_normalized}` })),
            ]}
          />
          <Pagination page={page} total={users.data?.total || 0} onChange={setPage} />
        </ResourceState>
        <ErrorMessage error={error} />
        <Button disabled={busy || users.loading}>Save assignment</Button>
      </form>
    </Card>
  );
}
export function Audit() {
  const [page, setPage] = useState(1);
  const resource = useResource(`/admin/audit?page=${page}`);
  return (
    <>
      <PageHeader title="Audit log" />
      <ResourceState resource={resource}>
        <Card>
          {resource.data?.items.map((e) => (
            <div className="list-row" key={e.id}>
              <div>
                <strong>{e.event_type || e.action}</strong>
                <p>
                  {e.timestamp} · {e.entity_id || e.target_id}
                </p>
                <small>
                  Actor: {e.actor_id} · {e.before ?? '—'} → {e.after ?? '—'}
                </small>
              </div>
            </div>
          ))}
        </Card>
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
    </>
  );
}
