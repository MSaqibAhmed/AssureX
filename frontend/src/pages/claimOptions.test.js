import { describe, it, expect } from 'vitest';
import { faultOptions, damageOptions, preserveSavedOption } from './claimOptions';

describe('claim dropdown options', () => {
  it('keeps policy values and explicit unknown damage', () => {
    expect(faultOptions.map((o) => o.value)).toEqual(expect.arrayContaining(['display','battery','audio','mechanical','electrical','heating']));
    expect(damageOptions.map((o) => o.value)).toEqual(expect.arrayContaining(['','none','liquid','accidental','commercial','consumable']));
  });
  it('preserves previously typed values without duplicates or mutation', () => {
    expect(preserveSavedOption(faultOptions, 'custom fault').at(-1).value).toBe('custom fault');
    expect(preserveSavedOption(faultOptions, 'display')).toBe(faultOptions);
    expect(faultOptions.some((o) => o.value === 'custom fault')).toBe(false);
  });
});
