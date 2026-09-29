import { useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, API_BASE, downloadBlob } from '../api/client';
import { useResource, ResourceState, ErrorMessage, Pagination } from '../api/hooks';
import {
  Badge,
  Banner,
  Button,
  Card,
  Dialog,
  Input,
  PageHeader,
  Select,
  Textarea,
} from '../components/ui';
import ClaimStages from '../components/ClaimStages';
import DocumentPreview from '../components/DocumentPreview';
import ClaimSummary from '../components/ClaimSummary';
import { faultOptions, damageOptions, preserveSavedOption } from './claimOptions';

export function claimLink(id, role) {
  return role === 'reviewer'
    ? `/review/${id}`
    : role === 'service'
      ? `/service/claims/${id}`
      : role === 'admin'
        ? `/reports/claims/${id}`
        : `/claims/${id}`;
}
export function ClaimList({ title = 'Your claims' }) {
  const role = useSelector((s) => s.app.session.role);
  const [page, setPage] = useState(1);
  const [params] = useSearchParams();
  const [status, setStatus] = useState(params.get('status') || '');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('newest');
  const resource = useResource(
    `/reports?page=${page}&status=${encodeURIComponent(status)}&q=${encodeURIComponent(query)}&sort=${sort}`,
  );
  return (
    <>
      <PageHeader title={title} description="Track your claims and pick up where you left off.">
        {['customer', 'service'].includes(role) && (
          <Button to={role === 'service' ? '/service/claims/new' : '/claims/new'}>New claim</Button>
        )}
      </PageHeader>
      <div className="filter-bar">
        <Input
          label="Search claims"
          placeholder="Claim ID, product ID, serial or fault"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
        />
        <Select
          label="Order"
          value={sort}
          onChange={(e) => {
            setSort(e.target.value);
            setPage(1);
          }}
          options={[
            { value: 'newest', label: 'Newest first' },
            { value: 'oldest', label: 'Oldest first' },
          ]}
        />
        <Select
          label="Claim status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          options={[
            '',
            'Draft',
            'Submitted',
            'Under Evaluation',
            'Manual Review',
            'Approved',
            'Rejected',
            'Additional Information Required',
            'Closed',
          ]}
        />
      </div>
      <ResourceState resource={resource}>
        <Card>
          <div className="table-scroll">
            <table className="recent-table claim-list-table">
              <thead>
                <tr>
                  <th>Claim</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Version</th>
                </tr>
              </thead>
              <tbody>
                {resource.data?.items.map((c) => (
                  <tr key={c.id}>
                    <td data-label="Claim">
                      <Link to={claimLink(c.id, role)}>{c.public_claim_id}</Link>
                    </td>
                    <td data-label="Status">
                      <Badge status={c.status} />
                    </td>
                    <td data-label="Created">{new Date(c.created_at).toLocaleDateString()}</td>
                    <td data-label="Version">{c.version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {resource.data?.total === 0 && <p>No matching claims.</p>}
        </Card>
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
    </>
  );
}
export function ClaimWizard() {
  const { id } = useParams();
  const resource = useResource(id ? `/claims/${id}` : null);
  return (
    <>
      <PageHeader title={id ? 'Update claim facts' : 'Let’s start your claim.'} back="/claims" />
      <ClaimStages stage={0} />
      <ResourceState resource={resource}>
        <FactsForm key={resource.data?.version || 'new'} claim={resource.data} />
      </ResourceState>
    </>
  );
}
function FactsForm({ claim }) {
  const role = useSelector((s) => s.app.session.role);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [step, setStep] = useState(claim ? 1 : 0);
  const formRef = useRef(null);
  const products = useResource(claim ? null : `/products?page=${page}`);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const { product_id, ...facts } = values;
    for (const key of Object.keys(facts))
      if (!facts[key] && key !== 'description') facts[key] = null;
    try {
      const c = claim
        ? await api.patch(`/claims/${claim.id}`, {
            version: claim.version,
            status: claim.status,
            facts,
          })
        : await api.post('/claims', { product_id, facts });
      navigate(claimLink(c.id, role));
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  if (claim && !['Draft', 'Additional Information Required'].includes(claim.status))
    return (
      <Banner>
        This claim has been submitted. You can edit it if your reviewer requests changes.
      </Banner>
    );
  return (
    <Card title={step === 0 ? '1. Select your product' : '2. Describe the issue'}>
      <nav className="intake-steps" aria-label="Claim preparation">
        <span aria-current={step === 0 ? 'step' : undefined}>1 Product</span>
        <span aria-current={step === 1 ? 'step' : undefined}>2 Issue</span>
        <span>3 Evidence</span>
        <span>4 Review & submit</span>
      </nav>
      <form ref={formRef} onSubmit={save}>
        <div hidden={step !== 0}>
          {!claim && (
            <ResourceState resource={products}>
              <Select
                label="Product"
                name="product_id"
                defaultValue={params.get('product') || ''}
                required
                options={[
                  { value: '', label: 'Select a product' },
                  ...(products.data?.items || []).map((p) => ({
                    value: p.id,
                    label: `${p.brand} ${p.model} · ${p.serial}`,
                  })),
                ]}
              />
              <Pagination page={page} total={products.data?.total || 0} onChange={setPage} />
              {role === 'customer' ? (
                <Link to="/products/new">Register a product</Link>
              ) : (
                <p>Only products already assigned to your service center are available.</p>
              )}
            </ResourceState>
          )}
        </div>
        <div hidden={step !== 1}>
          <div className="form-grid">
            <Input
              label="Fault date"
              name="fault_date"
              type="date"
              defaultValue={claim?.facts.fault_date || ''}
              required
            />
            <Select
              label="Fault category"
              name="fault_category"
              defaultValue={claim?.facts.fault_category || ''}
              options={preserveSavedOption(faultOptions, claim?.facts.fault_category)}
              help="Select the issue you observed. Coverage is checked against your warranty policy."
              required
            />
            <Select
              label="Damage type"
              name="damage_type"
              defaultValue={claim?.facts.damage_type || ''}
              options={preserveSavedOption(damageOptions, claim?.facts.damage_type)}
              help="Select observed damage. If unsure, leave it as Not sure; add details in the description."
            />
            <Input
              label="Serial number"
              name="serial"
              defaultValue={claim?.facts.serial || ''}
              required
            />
            <Input
              label="Invoice number"
              name="invoice_number"
              defaultValue={claim?.facts.invoice_number || ''}
            />
          </div>
          <Textarea
            label="Fault description"
            name="description"
            defaultValue={claim?.facts.description || ''}
            maxLength={4000}
            required
          />
        </div>
        <ErrorMessage error={error} />
        <div className="form-actions">
          {step === 0 ? (
            <Button
              type="button"
              disabled={products.loading}
              onClick={() => {
                const select = formRef.current.elements.product_id;
                if (select?.reportValidity()) setStep(1);
              }}
            >
              Continue to issue
            </Button>
          ) : (
            <>
              {!claim && (
                <Button type="button" variant="secondary" onClick={() => setStep(0)}>
                  Back to product
                </Button>
              )}
              <Button type="submit" disabled={busy || products.loading}>
                {busy ? 'Saving…' : 'Save claim draft'}
              </Button>
            </>
          )}
        </div>
      </form>
    </Card>
  );
}
export function JobProgress({ id, onComplete, onStatus, analysis = false }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [retry, setRetry] = useState(0);
  const callback = useRef(onComplete);
  callback.current = onComplete;
  const statusCallback = useRef(onStatus);
  statusCallback.current = onStatus;
  useEffect(() => {
    let active = true;
    let timer;
    const controller = new AbortController();
    async function poll() {
      try {
        const value = await api.get(`/jobs/${id}`, { signal: controller.signal });
        if (!active) return;
        setJob(value);
        setError(null);
        statusCallback.current?.({ id, status: value.status });
        if (value.status === 'completed') callback.current?.(value);
        else if (value.status !== 'failed') timer = setTimeout(poll, 1000);
      } catch (error) {
        if (active) {
          setError(error);
          statusCallback.current?.({ id, status: 'unavailable' });
        }
      }
    }
    poll();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [id, retry]);
  const processing = !error && ['queued', 'running'].includes(job?.status);
  return (
    <div
      className={`processing-state ${analysis ? 'analysis-progress' : ''}`}
      role="status"
      aria-live="polite"
      data-testid="job-progress"
    >
      {analysis && (
        <>
          <div className="analysis-progress-heading">
            <span className="analysis-orb" aria-hidden="true">
              {processing ? <span className="analysis-spinner" /> : 'AI'}
            </span>
            <div>
              <span className="eyebrow">INDEPENDENT CLAIM ANALYSIS</span>
              <h3>
                {error
                  ? 'Connection interrupted'
                  : job?.status === 'failed'
                    ? 'Analysis needs attention'
                    : job?.status === 'completed'
                      ? 'Analysis completed'
                      : job?.status === 'queued'
                        ? 'Your claim is queued'
                        : job?.stage === 'models'
                          ? 'Evaluating your claim'
                          : 'Preparing claim analysis'}
              </h3>
              <p>
                {error
                  ? 'We cannot confirm progress. Retry to reconnect.'
                  : job?.status === 'completed'
                    ? 'Loading the recorded recommendation and rule findings.'
                    : job?.status === 'failed'
                      ? 'Your claim is saved. Processing did not complete.'
                      : 'Python and image models evaluate independently. Results appear when processing completes.'}
              </p>
            </div>
          </div>
          {processing && (
            <div className="analysis-sweep" aria-hidden="true">
              <span />
            </div>
          )}
        </>
      )}
      <p>
        Job {id}: {job?.status || 'loading'} · {job?.stage || 'Awaiting server status'}
      </p>
      {job?.status === 'failed' && (
        <Banner tone="error">
          Processing failed:{' '}
          {typeof job.error === 'string'
            ? job.error
            : JSON.stringify(job.error || 'See server logs')}
        </Banner>
      )}
      <ErrorMessage error={error} />
      {error && <Button onClick={() => setRetry((n) => n + 1)}>Retry polling</Button>}
    </div>
  );
}
export function Evidence({ claim, refresh }) {
  const role = useSelector((s) => s.app.session.role);
  const documents = useResource(`/claims/${claim.id}/documents`);
  const editable = ['Draft', 'Additional Information Required'].includes(claim.status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(null);
  async function upload(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = new FormData(form);
    const file = body.get('file');
    if (!file?.size || file.size > 10 * 1024 * 1024) {
      setError(new Error('Select a nonempty supported file up to 10 MiB.'));
      return;
    }
    body.set('version', claim.version);
    body.set('status', claim.status);
    setBusy(true);
    setError(null);
    try {
      await api.post(`/claims/${claim.id}/documents`, body, {
        onUploadProgress: (event) =>
          setProgress(event.total ? Math.round((event.loaded * 100) / event.total) : null),
      });
      form.reset();
      documents.reload();
      refresh();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }
  return (
    <Card title="Evidence and OCR">
      {editable && ['customer', 'service'].includes(role) && (
        <>
          <form onSubmit={upload}>
            <Select
              label="Document type"
              name="document_type"
              options={['receipt', 'serial_photo', 'warranty', 'diagnostic', 'supporting']}
            />
            <Input
              label="Evidence file"
              name="file"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              required
              help="Up to 10 MiB; PDF maximum 10 pages. Server validates file contents."
            />
            <Button disabled={busy} type="submit">
              {busy ? `Uploading ${progress ?? ''}%` : 'Upload document'}
            </Button>
          </form>
          <section className="section-spaced">
            <h3>Fault image / video</h3>
            <p>
              Show the affected part clearly. Videos go to a human reviewer. Image AI requires a
              dedicated fault-detection model; until enabled, photos also receive human review.
            </p>
            <form onSubmit={upload}>
              <Select
                label="Fault evidence type"
                name="document_type"
                options={['fault_image', 'fault_video']}
              />
              <Input
                label="Fault image or video"
                name="file"
                type="file"
                accept=".png,.jpg,.jpeg,.mp4"
                required
                help="JPEG/PNG image or MP4 video, up to 10 MiB. Select the matching evidence type."
              />
              <Button disabled={busy} type="submit">
                {busy ? 'Uploading…' : 'Upload fault evidence'}
              </Button>
            </form>
          </section>
        </>
      )}
      <ErrorMessage error={error} />
      <ResourceState resource={documents}>
        {documents.data?.map((d) => (
          <Document
            key={d.id}
            document={d}
            editable={editable && ['customer', 'service'].includes(role)}
            refresh={refresh}
          />
        ))}
        {documents.data?.length === 0 && <p>No documents uploaded.</p>}
      </ResourceState>
    </Card>
  );
}
function Document({ document, editable, refresh }) {
  const resource = useResource(`/documents/${document.id}/ocr`);
  const [error, setError] = useState(null);
  async function download() {
    try {
      const data = await api.get(`/documents/${document.id}/ocr`);
      const url = new URL(data.download_url, new URL(API_BASE, window.location.origin));
      downloadBlob(await api.get(url.href, { responseType: 'blob' }), document.name);
    } catch (error) {
      setError(error);
    }
  }
  return (
    <section className="section-spaced" data-testid="document">
      <h3>
        {document.name} · {document.type}
      </h3>
      <Button variant="secondary" onClick={download}>
        Download evidence
      </Button>
      <JobProgress id={document.job_id} onComplete={() => resource.reload()} />
      <ErrorMessage error={error} />
      <ResourceState resource={resource}>
        <div className="ocr-layout">
          <DocumentPreview document={document} />
          <div>
            <h3>
              {document.type.startsWith('fault_')
                ? 'Fault evidence review'
                : 'Extracted information'}
            </h3>
            {document.type.startsWith('fault_') && (
              <p role="status">
                {resource.data?.document?.media_analysis?.message ||
                  'Preparing fault evidence for review…'}
              </p>
            )}
            {resource.data?.fields.map((field) => (
              <OcrField
                key={field.id}
                field={field}
                editable={editable}
                onSaved={() => {
                  resource.reload();
                  refresh();
                }}
              />
            ))}
            {!document.type.startsWith('fault_') && resource.data?.fields.length === 0 && (
              <p>No extracted fields available yet.</p>
            )}
          </div>
        </div>
      </ResourceState>
    </section>
  );
}
function OcrField({ field, editable, onSaved }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const labels = {
    purchase_date: 'Purchase date',
    invoice_number: 'Invoice number',
    product: 'Product',
    model: 'Model',
    serial: 'Serial number',
    retailer: 'Retailer',
    amount: 'Purchase amount',
    warranty_duration: 'Warranty duration (months)',
  };
  const label = labels[field.field] || field.field.replaceAll('_', ' ');
  const value = field.normalized_value ?? field.raw_value;
  const reliable = field.corrected || (field.normalized_value != null && field.confidence >= 0.8);
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/ocr-fields/${field.id}`, {
        normalized_value: new FormData(event.currentTarget).get('value'),
      });
      onSaved();
      setEditing(false);
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save} data-testid={`ocr-${field.field}`}>
      {!editing ? (
        <div className="list-row">
          <div>
            <strong>{label}</strong>
            <p>{value || 'Not detected in document'}</p>
            <small>
              {field.corrected
                ? 'Confirmed/corrected'
                : reliable
                  ? 'Extracted automatically'
                  : 'Extracted automatically · may need review'}
            </small>
          </div>
          {editable && (
            <Button type="button" variant="secondary" onClick={() => setEditing(true)}>
              Correct details
            </Button>
          )}
        </div>
      ) : (
        <>
          <Input
            label={`OCR ${field.field}`}
            name="value"
            defaultValue={field.normalized_value || field.raw_value || ''}
            readOnly={!editable}
            required
          />
          {editable && (
            <Button variant="secondary" disabled={busy}>
              Confirm / correct
            </Button>
          )}
          <Button type="button" variant="secondary" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </>
      )}
      <ErrorMessage error={error} />
    </form>
  );
}
export function Evaluation({ evaluation }) {
  if (!evaluation) return <Banner>Your analysis will appear here when it is ready.</Banner>;
  return (
    <Card title="Independent model analysis">
      <div data-testid="evaluation" data-evaluation-id={evaluation.id}>
        <div className="recommendation-panel">
          <span className="eyebrow">AI RECOMMENDATION</span>
          <h3 data-testid="recommendation">{evaluation.recommendation}</h3>
          <p>Advisory recommendation — not a human approval.</p>
        </div>
        <Badge status={evaluation.comparison.status} />
        <p>
          Confidence difference:{' '}
          {evaluation.comparison.difference == null
            ? 'Unavailable'
            : `${(evaluation.comparison.difference * 100).toFixed(2)} percentage points`}
        </p>
        <div className="two-col">
          {['python', 'gtm'].map((family) => (
            <div key={family} className="model-card">
              <h3>{family === 'python' ? 'Python model' : 'Google Teachable Machine'}</h3>
              <small>
                {family === 'python' ? 'Structured claim data' : 'Claim summary card image'}
              </small>
              <p>Version: {evaluation.versions[family]}</p>
              {evaluation.predictions[family] ? (
                Object.entries(evaluation.predictions[family]).map(([label, value]) => (
                  <div key={label} className="confidence-row" data-testid={`${family}-${label}`}>
                    <div className="confidence-label">
                      <span>{label.replaceAll('_', ' ')}</span>
                      <strong>{(value * 100).toFixed(2)}%</strong>
                    </div>
                    <div className="confidence-track">
                      <span style={{ width: `${value * 100}%` }} />
                    </div>
                  </div>
                ))
              ) : (
                <p>Output unavailable</p>
              )}
            </div>
          ))}
        </div>
        <h3 className="section-spaced">Policy validation</h3>
        <p>Policy version: {evaluation.versions.policy}</p>
        {evaluation.reasons.map((r, i) => (
          <p key={i}>{r}</p>
        ))}
        {evaluation.rule_results.map((r) => (
          <div className="list-row" key={r.rule_id}>
            <span>
              {r.rule_id}: {r.explanation}
            </span>
            <Badge status={r.status} />
          </div>
        ))}
      </div>
    </Card>
  );
}
export function ClaimDetail() {
  const { id } = useParams();
  const role = useSelector((s) => s.app.session.role);
  const resource = useResource(`/claims/${id}`);
  const evaluations = useResource(`/claims/${id}/evaluations`);
  const assistance = useResource(`/claims/${id}/assistance`);
  const workflow = useResource(`/claims/${id}/workflow`);
  const [selectedEvaluation, setSelectedEvaluation] = useState('');
  const [jobParams, setJobParams] = useSearchParams();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const jobId =
    jobParams.get('job') ||
    (['Submitted', 'Under Evaluation'].includes(resource.data?.status)
      ? workflow.data?.evaluation_job?.id
      : null);
  const [liveJob, setLiveJob] = useState(null);
  const processing =
    ['Submitted', 'Under Evaluation'].includes(resource.data?.status) &&
    ['queued', 'running'].includes(
      liveJob?.id === jobId ? liveJob.status : workflow.data?.evaluation_job?.status,
    );
  const attempt = useRef(null);
  const claim = resource.data;
  const latestEvaluation = evaluations.data?.find((e) => e.id === claim?.latest_evaluation_id);
  const evaluation = evaluations.data?.find(
    (e) => e.id === (selectedEvaluation || claim?.latest_evaluation_id),
  );
  function refresh() {
    resource.reload();
    assistance.reload();
    workflow.reload();
  }
  async function submit() {
    setBusy(true);
    setError(null);
    // Preserve the same body/key on an ambiguous network failure; a new version gets a new key.
    if (!attempt.current || attempt.current.version !== claim.version)
      attempt.current = { version: claim.version, status: claim.status, key: crypto.randomUUID() };
    const { key, ...body } = attempt.current;
    try {
      const result = await api.post(`/claims/${id}/submit`, body, {
        headers: { 'Idempotency-Key': key },
      });
      setJobParams({ job: result.job_id });
      refresh();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <ResourceState resource={resource}>
      {claim && (
        <>
          <PageHeader
            title={claim.public_claim_id}
            description="Your product, evidence and claim progress."
            back={
              role === 'reviewer'
                ? '/review'
                : role === 'service'
                  ? '/service/queue'
                  : role === 'admin'
                    ? '/reports'
                    : '/claims'
            }
          >
            <Badge status={claim.status} />
            <Button
              variant="secondary"
              onClick={() => {
                refresh();
                evaluations.reload();
              }}
            >
              Refresh claim
            </Button>
          </PageHeader>
          <ErrorMessage error={error} />
          <ClaimStages
            processing={processing}
            stage={
              ['Draft', 'Additional Information Required'].includes(claim.status)
                ? 0
                : ['Submitted', 'Under Evaluation'].includes(claim.status)
                  ? 1
                  : 2
            }
          />
          <ClaimSummary key={`${claim.id}-${claim.version}`} claim={claim} workflow={workflow} />
          <div className="detail-grid">
            <div className="stack">
              <Card title="Claim facts">
                {Object.entries(claim.facts).map(([key, value]) => (
                  <p key={key}>
                    <strong>
                      {key.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())}:
                    </strong>{' '}
                    {value ?? 'Not supplied'}
                  </p>
                ))}
                <p>Version: {claim.version}</p>
                {['customer', 'service'].includes(role) &&
                  ['Draft', 'Additional Information Required'].includes(claim.status) && (
                    <>
                      <Button
                        to={
                          role === 'service' ? `/service/claims/${id}/edit` : `/claims/${id}/edit`
                        }
                        variant="secondary"
                      >
                        Edit facts
                      </Button>
                    </>
                  )}
              </Card>
              {['Draft', 'Additional Information Required'].includes(claim.status) && (
                <Evidence claim={claim} refresh={refresh} />
              )}
              {['customer', 'service'].includes(role) &&
                ['Draft', 'Additional Information Required'].includes(claim.status) && (
                  <Card title="Submit for analysis">
                    <p>
                      Check your details and confirm the information extracted from your documents.
                    </p>
                    <p>
                      Documents still processing:{' '}
                      {assistance.data?.pending_document_jobs ?? 'Checking…'}
                    </p>
                    <Button
                      onClick={submit}
                      disabled={
                        busy ||
                        assistance.loading ||
                        Boolean(assistance.error) ||
                        assistance.data?.pending_document_jobs > 0
                      }
                    >
                      {busy ? 'Submitting…' : 'Submit claim'}
                    </Button>
                    <Button variant="secondary" onClick={assistance.reload}>
                      Check readiness
                    </Button>
                  </Card>
                )}
              {jobId && (
                <JobProgress
                  id={jobId}
                  analysis
                  onStatus={setLiveJob}
                  onComplete={() => {
                    setJobParams({});
                    refresh();
                    evaluations.reload();
                  }}
                />
              )}
              <ResourceState resource={evaluations}>
                {evaluations.data?.length > 1 && (
                  <Select
                    label="Evaluation history"
                    value={selectedEvaluation || claim.latest_evaluation_id}
                    onChange={(e) => setSelectedEvaluation(e.target.value)}
                    options={evaluations.data.map((e, i) => ({
                      value: e.id,
                      label: `Evaluation ${i + 1} · ${e.id}${e.id === claim.latest_evaluation_id ? ' (current)' : ''}`,
                    }))}
                  />
                )}
                <Evaluation evaluation={evaluation} />
              </ResourceState>
              {!['Draft', 'Additional Information Required'].includes(claim.status) && (
                <details className="card">
                  <summary>Evidence & extracted information</summary>
                  <Evidence claim={claim} refresh={refresh} />
                </details>
              )}
              <Card title="Decision history">
                <ResourceState resource={workflow}>
                  {workflow.data?.reviews.map((r) => (
                    <div className="list-row" key={r.id}>
                      <div>
                        <strong>{r.after}</strong>
                        <p>{r.reason}</p>
                        <small>
                          {r.timestamp} · Evaluation {r.evaluation_id}
                        </small>
                      </div>
                    </div>
                  ))}
                  {!workflow.data?.reviews.length && <p>No human decision recorded yet.</p>}
                </ResourceState>
              </Card>
              <Card title="Claim timeline">
                <ResourceState resource={workflow}>
                  <ol className="timeline">
                    <li>
                      <div>
                        <strong>Claim created</strong>
                        <small>{new Date(claim.created_at).toLocaleString()}</small>
                      </div>
                    </li>
                    {workflow.data?.timeline?.map((event) => (
                      <li key={event.id}>
                        <div>
                          <strong>{event.action.replaceAll('_', ' ')}</strong>
                          <p>{event.after || ''}</p>
                          <small>
                            {new Date(event.timestamp).toLocaleString()} ·{' '}
                            {event.actor_id === 'worker' ? 'Processing service' : 'Authorized user'}
                          </small>
                        </div>
                      </li>
                    ))}
                  </ol>
                </ResourceState>
              </Card>
              <Comments id={id} role={role} />
            </div>
            <div className="stack">
              <Card title="Next steps">
                <ResourceState resource={assistance}>
                  {assistance.data && (
                    <>
                      <p>Reporting deadline: {assistance.data.deadline || 'Unavailable'}</p>
                      <p>{assistance.data.requested_information}</p>
                      <p>Missing fields: {assistance.data.missing_fields.join(', ') || 'None'}</p>
                      <p>
                        Missing documents: {assistance.data.missing_documents.join(', ') || 'None'}
                      </p>
                      {assistance.data.corrective_actions.map((a) => (
                        <p key={a}>{a}</p>
                      ))}
                    </>
                  )}
                </ResourceState>
              </Card>
              {role !== 'customer' && <Summary id={id} />}
              {role === 'reviewer' && claim.status === 'Manual Review' && latestEvaluation && (
                <ReviewForm claim={claim} refresh={refresh} />
              )}
              {role === 'service' && (
                <Card title="Service records">
                  <Button to={`/service/claims/${id}/repair`}>Record repair</Button>
                  <Button to={`/service/claims/${id}/replacement`}>Record replacement</Button>
                </Card>
              )}
              {evaluation && <ReportDownload claim={claim} evaluation={evaluation} />}
            </div>
          </div>
        </>
      )}
    </ResourceState>
  );
}
function Summary({ id }) {
  const resource = useResource(`/claims/${id}/summary`);
  return (
    <Card title="Claim summary">
      {resource.error?.status === 404 ? (
        <>
          <p>Summary not ready.</p>
          <Button onClick={resource.reload}>Refresh summary</Button>
        </>
      ) : (
        <ResourceState resource={resource}>
          <p>{resource.data?.text}</p>
          <small>
            {resource.data?.source === 'local_model'
              ? 'Local model summary'
              : 'Structured factual summary'}{' '}
            · {resource.data?.model_version}
          </small>
        </ResourceState>
      )}
    </Card>
  );
}
function Comments({ id, role }) {
  const resource = useResource(`/claims/${id}/comments`);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function send(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = Object.fromEntries(new FormData(form));
    setBusy(true);
    setError(null);
    try {
      await api.post(`/claims/${id}/comments`, { visibility: 'customer', ...body });
      form.reset();
      resource.reload();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Messages">
      <ResourceState resource={resource}>
        {resource.data?.map((c) => (
          <div className="list-row" key={c.id}>
            <div>
              <p>{c.message}</p>
              <small>
                {c.timestamp} · {c.visibility}
              </small>
            </div>
          </div>
        ))}
      </ResourceState>
      <form onSubmit={send}>
        <Textarea label="Message" name="message" required maxLength={4000} />
        {role !== 'customer' && (
          <Select label="Visibility" name="visibility" options={['customer', 'staff']} />
        )}
        <ErrorMessage error={error} />
        <Button disabled={busy}>Send message</Button>
      </form>
    </Card>
  );
}
export function ReviewForm({ claim, refresh }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(null);
  function prepare(event) {
    event.preventDefault();
    setPending(Object.fromEntries(new FormData(event.currentTarget)));
  }
  async function save() {
    if (busy || !pending) return;
    setBusy(true);
    setError(null);
    const values = pending;
    setPending(null);
    try {
      await api.post(`/claims/${claim.id}/reviews`, {
        ...values,
        version: claim.version,
        status: claim.status,
        evaluation_id: claim.latest_evaluation_id,
      });
      refresh();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Reviewer decision">
      <form onSubmit={prepare}>
        <Select
          label="Decision"
          name="action"
          options={[
            { value: 'approve', label: 'Approve' },
            { value: 'reject', label: 'Reject' },
            { value: 'request_info', label: 'Request information' },
          ]}
        />
        <Textarea label="Decision reason" name="reason" required maxLength={4000} />
        <ErrorMessage error={error} />
        <Button disabled={busy}>Save decision</Button>
      </form>
      {pending && (
        <Dialog
          title="Confirm reviewer decision"
          onClose={() => setPending(null)}
          onConfirm={save}
          confirmLabel="Confirm decision"
          danger={pending.action === 'reject'}
        >
          <p>
            You are recording: <strong>{pending.action.replaceAll('_', ' ')}</strong>.
          </p>
          <p>{pending.reason}</p>
          <p>
            The original AI evaluation will remain unchanged in history. Confirm that you have
            reviewed the evidence and explained any override.
          </p>
        </Dialog>
      )}
    </Card>
  );
}
function ReportDownload({ claim, evaluation }) {
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);
  async function download() {
    setDownloading(true);
    setError(null);
    try {
      const query = new URLSearchParams({ evaluation_id: evaluation.id });
      if (claim.latest_review_id && claim.latest_evaluation_id === evaluation.id)
        query.set('review_id', claim.latest_review_id);
      downloadBlob(
        await api.get(`/claims/${claim.id}/report?${query}`, { responseType: 'blob' }),
        `claim-${claim.public_claim_id}.pdf`,
      );
    } catch (error) {
      setError(error);
    } finally {
      setDownloading(false);
    }
  }
  return (
    <Card
      title="Pinned report"
      subtitle="A detailed PDF of this assessment, evidence checks and the selected reviewer decision."
    >
      <p>Evaluation: {evaluation.id}</p>
      <Button onClick={download} disabled={downloading}>
        {downloading ? 'Preparing PDF�' : 'Download PDF report'}
      </Button>
      <ErrorMessage error={error} />
    </Card>
  );
}
export function ClaimReport() {
  return <ClaimDetail />;
}
export function ClaimResult() {
  return <LegacyClaimRedirect />;
}
export function Processing() {
  return <LegacyClaimRedirect />;
}
export function InformationForm() {
  return <LegacyClaimRedirect />;
}
export function RequestReview() {
  return <LegacyClaimRedirect />;
}
export function LegacyClaimRedirect() {
  const { id } = useParams();
  const role = useSelector((s) => s.app.session.role);
  const [params] = useSearchParams();
  return <Navigate to={`${claimLink(id, role)}${params.size ? `?${params}` : ''}`} replace />;
}
