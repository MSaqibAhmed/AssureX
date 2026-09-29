import { useState } from 'react';
import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { api, API_BASE, downloadBlob } from '../api/client';
import { useResource, ResourceState, ErrorMessage, Pagination } from '../api/hooks';
import { Button, Card, PageHeader, Select } from '../components/ui';
import { claimLink } from './Claims';

export function DocumentLibrary({ productId }) {
  const role = useSelector((s) => s.app.session.role);
  const [page, setPage] = useState(1);
  const [error, setError] = useState(null);
  const resource = useResource(
    `/documents?page=${page}${productId ? `&product_id=${productId}` : ''}`,
  );
  async function download(document) {
    try {
      const data = await api.get(`/documents/${document.id}/ocr`);
      const url = new URL(data.download_url, new URL(API_BASE, window.location.origin));
      downloadBlob(await api.get(url.href, { responseType: 'blob' }), document.name);
    } catch (error) {
      setError(error);
    }
  }
  return (
    <>
      <PageHeader
        title="Documents"
        description="Private evidence organized by product and claim. Upload or verify evidence inside its claim."
      />
      <ErrorMessage error={error} />
      <ResourceState resource={resource}>
        <Card>
          {resource.data?.items.map((d) => (
            <div className="list-row" key={d.id}>
              <div>
                <strong>{d.name}</strong>
                <p>
                  {d.type} · {(d.size / 1024).toFixed(1)} KB
                </p>
                <Link to={claimLink(d.claim_id, role)}>Open claim / verify OCR</Link>
              </div>
              <Button variant="secondary" onClick={() => download(d)}>
                Download
              </Button>
            </div>
          ))}
          {resource.data?.total === 0 && (
            <p>No evidence yet. Start a claim and upload its documents.</p>
          )}
        </Card>
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
    </>
  );
}
export function ServiceRecords({ productId }) {
  const [page, setPage] = useState(1);
  const resource = useResource(
    productId ? `/products/${productId}/service-history` : `/service-history?page=${page}`,
  );
  const rows = productId ? resource.data : resource.data?.items;
  return (
    <>
      <PageHeader title="Service history" description="Recorded repairs and replacements." />
      <ResourceState resource={resource}>
        <Card>
          {rows?.map((r) => (
            <div className="list-row" key={r.id}>
              <div>
                <strong>
                  {r.kind} · {r.date}
                </strong>
                <p>{r.notes}</p>
                <p>
                  Authorization:{' '}
                  {r.authorized === null ? 'Unknown' : r.authorized ? 'Authorized' : 'Unauthorized'}
                </p>
                {r.parts && <p>Parts: {r.parts}</p>}
                {r.outcome && <p>Outcome: {r.outcome}</p>}
                {r.cost !== undefined && <p>Cost: {r.cost}</p>}
                {r.new_serial && (
                  <p>
                    {r.old_serial} → {r.new_serial}
                  </p>
                )}
              </div>
            </div>
          ))}
          {rows?.length === 0 && <p>No service records.</p>}
        </Card>
        {!productId && (
          <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
        )}
      </ResourceState>
    </>
  );
}
export function PolicyPicker({ category, initial = '' }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(initial);
  const resource = useResource(
    category ? `/policies?category=${encodeURIComponent(category)}&page=${page}` : null,
  );
  const detail = useResource(selected ? `/policies/${selected}` : null);
  return (
    <>
      <ResourceState resource={resource}>
        <Select
          label="Warranty policy"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          name="policy_version_id"
          required
          options={[
            { value: '', label: 'Select existing coverage policy' },
            ...(selected && !resource.data?.items.some((p) => p.id === selected)
              ? [
                  {
                    value: selected,
                    label: detail.data
                      ? `${detail.data.category} · v${detail.data.version}`
                      : 'Selected existing policy',
                  },
                ]
              : []),
            ...(resource.data?.items || []).map((p) => ({
              value: p.id,
              label: `${p.category} · v${p.version} · ${p.policy.coverage_months} months`,
            })),
          ]}
        />
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
      {detail.data && (
        <div className="field-help">
          Covered faults:{' '}
          {detail.data.policy.covered_fault_categories.join(', ') || 'See provider terms'}.
          Exclusions: {detail.data.policy.excluded_damage.join(', ') || 'None listed'}. Required
          evidence: {detail.data.policy.required_documents.join(', ')}.
        </div>
      )}
    </>
  );
}
