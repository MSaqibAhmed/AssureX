import { describe, expect, it } from 'vitest';
import { api, normalizeError, setCsrf } from './client';
describe('shared API contract', () => {
  it('unwraps real envelopes and sends cookies and CSRF', async () => {
    setCsrf('csrf-test');
    const data = await api.post(
      '/claims',
      { facts: {} },
      {
        adapter: async (config) => {
          expect(config.withCredentials).toBe(true);
          expect(config.headers['X-CSRF-Token']).toBe('csrf-test');
          return {
            data: { data: { id: 'server-id' }, version: 1, request_id: 'trace' },
            status: 201,
            headers: {},
            config,
          };
        },
      },
    );
    expect(data).toEqual({ id: 'server-id' });
    setCsrf(null);
  });
  it('preserves status and structured field errors', () => {
    const error = normalizeError({
      response: {
        status: 422,
        data: {
          code: 'invalid_input',
          message: 'Invalid request',
          field_errors: { 'body.serial': 'Required' },
        },
      },
    });
    expect(error.status).toBe(422);
    expect(error.code).toBe('invalid_input');
    expect(error.field_errors['body.serial']).toBe('Required');
  });
});
