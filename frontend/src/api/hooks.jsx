import { useCallback, useEffect, useState } from 'react';
import { api } from './client';
import { Banner, Button, Card } from '../components/ui';
import { notifyError } from '../components/notifications';
export function useResource(path) {
  const [state, setState] = useState({ data: null, loading: !!path, error: null });
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((r) => r + 1), []);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    if (!path) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    setState({ data: null, loading: true, error: null });
    api
      .get(path, { signal: controller.signal })
      .then((data) => {
        if (active) setState({ data, loading: false, error: null });
      })
      .catch((error) => {
        if (active) setState({ data: null, loading: false, error });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [path, revision]);
  return { ...state, reload };
}
export function ErrorMessage({ error }) {
  useEffect(() => {
    notifyError(error);
  }, [error]);
  return error ? (
    <div role="alert">
      {Object.entries(error.field_errors || {}).map(([key, value]) => (
        <p className="field-error" key={key}>
          {key}: {value}
        </p>
      ))}
    </div>
  ) : null;
}
export function ResourceState({ resource, children }) {
  if (resource.loading) return <p role="status">Loading from server…</p>;
  if (resource.error)
    return (
      <>
        <ErrorMessage error={resource.error} />
        <p className="field-help">Could not load these details.</p>
        <Button onClick={resource.reload}>Retry</Button>
      </>
    );
  return children;
}
export function Unavailable({ title = 'Not available', children }) {
  return (
    <Card title={title}>
      <Banner>
        {children || 'This feature has no backend endpoint yet. No changes can be saved here.'}
      </Banner>
    </Card>
  );
}
export function Pagination({ page, total, limit = 20, onChange }) {
  return (
    <div className="form-actions">
      <Button
        type="button"
        variant="secondary"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Previous
      </Button>
      <span>
        Page {page} · {total} records
      </span>
      <Button
        type="button"
        variant="secondary"
        disabled={page * limit >= total}
        onClick={() => onChange(page + 1)}
      >
        Next
      </Button>
    </div>
  );
}
