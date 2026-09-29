import { toast } from 'react-toastify';

export function notifyError(error) {
  if (!error || error.code === 'ERR_CANCELED') return;
  const message =
    error.status === 409
      ? 'This record changed. Refresh and try again.'
      : error.status === 413
        ? 'File too large. Choose a file under 10 MB.'
        : error.status === 422
          ? error.message || 'Check the form and try again.'
          : error.status >= 500
            ? 'Something went wrong. Please try again.'
            : !error.status && error.code === 'network_error'
              ? 'Connection lost. Please try again.'
              : error.message || 'Could not save. Please try again.';
  toast.error(message, { toastId: `error-${message}` });
}

export function notifySaved(config) {
  if (typeof window === 'undefined' || !['post', 'patch', 'delete'].includes(config.method)) return;
  const path = config.url.split('?')[0];
  const message = path.endsWith('/auth/login')
    ? 'Signed in.'
    : path.endsWith('/auth/register')
      ? 'Account created.'
      : path.endsWith('/auth/logout')
        ? 'Signed out.'
        : path.endsWith('/submit')
          ? 'Claim submitted.'
          : path.endsWith('/documents')
            ? 'File uploaded.'
            : path.endsWith('/reviews')
              ? 'Decision saved.'
              : path.endsWith('/comments')
                ? 'Message sent.'
                : path.endsWith('/me')
                  ? 'Profile saved.'
                  : path.endsWith('/model-activations')
                    ? 'Model activated.'
                    : path.endsWith('/admin/users')
                      ? 'Account created.'
                      : path.endsWith('/admin/policies')
                        ? 'Policy created.'
                        : path.includes('/notifications/')
                          ? null
                          : 'Changes saved.';
  if (message) toast.success(message);
}
