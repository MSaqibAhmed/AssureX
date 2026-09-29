import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { ErrorMessage } from '../api/hooks';
import { Button } from './ui';
export default function DocumentPreview({ document }) {
  const [source, setSource] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState(1);
  useEffect(() => {
    let active = true;
    let objectUrl;
    const controller = new AbortController();
    async function load() {
      try {
        const blob = await api.get(`/documents/${document.id}/preview?page=${page}`, {
          responseType: 'blob',
          signal: controller.signal,
        });
        if (active) {
          objectUrl = URL.createObjectURL(blob);
          setSource(objectUrl);
          setError(null);
        }
      } catch (error) {
        if (active) setError(error);
      }
    }
    load();
    return () => {
      active = false;
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [document.id, attempt, page]);
  return (
    <div>
      <h3>Source document</h3>
      <p className="small muted">
        {document.type?.startsWith('fault_') ? 'Fault evidence for review. Visible appearance alone cannot confirm warranty eligibility.' : 'Compare the source with extracted fields. OCR confidence is not proof of authenticity.'}
      </p>
      <ErrorMessage error={error} />
      {error ? (
        <Button type="button" onClick={() => setAttempt((n) => n + 1)}>
          Retry preview
        </Button>
      ) : source ? (
        document.mime === 'video/mp4' ? <video className="source-preview" src={source} controls preload="metadata" aria-label={`Fault video: ${document.name}`} /> : <img className="source-preview" src={source} alt={`Source evidence: ${document.name}`} />
      ) : (
        <p role="status">Loading secure preview…</p>
      )}
      {document.mime === 'application/pdf' && (
        <label>
          PDF page
          <select
            aria-label={`Preview page for ${document.name}`}
            value={page}
            onChange={(e) => {
              setSource(null);
              setError(null);
              setPage(Number(e.target.value));
            }}
          >
            {Array.from({ length: 10 }, (_, i) => (
              <option key={i + 1} value={i + 1}>
                {i + 1}
              </option>
            ))}
          </select>
          <small>
            Select a page (up to the 10-page upload limit). Unavailable pages show an error.
          </small>
        </label>
      )}
    </div>
  );
}
