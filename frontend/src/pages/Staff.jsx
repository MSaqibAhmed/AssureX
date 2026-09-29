import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useResource, ResourceState, ErrorMessage } from '../api/hooks';
import { ServiceRecords } from './Records';
import { Button, Card, Input, PageHeader, Select, Textarea } from '../components/ui';
import { ClaimList, ClaimDetail, LegacyClaimRedirect } from './Claims';
export function WorkQueue({ review }) {
  return <ClaimList title={review ? 'Review queue' : 'Service work queue'} />;
}
export function ReviewWorkspace() {
  return <ClaimDetail />;
}
export function RequestInformation() {
  return <LegacyClaimRedirect />;
}
export function DecisionSaved() {
  return <LegacyClaimRedirect />;
}
export function ServiceDetail() {
  return <ClaimDetail />;
}
export function ServiceHistory() {
  return <ServiceRecords />;
}
export function ServiceForm() {
  const { id, type } = useParams();
  const navigate = useNavigate();
  const resource = useResource(`/claims/${id}`);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const replacement = type === 'replacement';
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    values.authorized = values.authorized === 'unknown' ? null : values.authorized === 'true';
    setBusy(true);
    setError(null);
    try {
      await api.post(
        `/products/${resource.data.product_id}/${replacement ? 'replacements' : 'repairs'}`,
        { ...values, claim_id: id },
      );
      navigate(`/service/claims/${id}`);
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader title={replacement ? 'Record replacement' : 'Record repair'} />
      <ResourceState resource={resource}>
        <Card>
          <form onSubmit={save}>
            <Input label="Service date" name="date" type="date" required />
            <Select
              label="Authorized repair"
              name="authorized"
              options={[
                { value: 'unknown', label: 'Unknown' },
                { value: 'true', label: 'Authorized' },
                { value: 'false', label: 'Unauthorized' },
              ]}
            />
            {replacement && (
              <>
                <Input label="Old serial" name="old_serial" required />
                <Input label="New serial" name="new_serial" required />
              </>
            )}
            <Textarea label="Service notes" name="notes" required />
            <Input label="Parts replaced" name="parts" maxLength={1000} />
            <Input label="Repair outcome" name="outcome" maxLength={1000} />
            <Input
              label="Repair cost"
              name="cost"
              type="number"
              min="0"
              step="0.01"
              defaultValue="0"
            />
            <ErrorMessage error={error} />
            <Button disabled={busy}>Save service record</Button>
          </form>
        </Card>
      </ResourceState>
    </>
  );
}
