// Values match the existing policy vocabulary; labels are user-facing only.
export const faultOptions = [
  { value: '', label: 'Select fault category' },
  { value: 'display', label: 'Display / screen issue' },
  { value: 'battery', label: 'Battery issue' },
  { value: 'audio', label: 'Audio / speaker issue' },
  { value: 'mechanical', label: 'Mechanical / moving parts issue' },
  { value: 'electrical', label: 'Electrical / power issue' },
  { value: 'heating', label: 'Heating issue' },
  { value: 'other', label: 'Other — explain in fault description' },
];
export const damageOptions = [
  { value: '', label: 'Not sure / not provided' },
  { value: 'none', label: 'No observed damage' },
  { value: 'liquid', label: 'Liquid / water damage' },
  { value: 'accidental', label: 'Accidental / physical damage' },
  { value: 'commercial', label: 'Damage from commercial use' },
  { value: 'consumable', label: 'Consumable part wear / damage' },
  { value: 'other', label: 'Other — explain in fault description' },
];
export function preserveSavedOption(options, value) {
  return value && !options.some((option) => option.value === value)
    ? [...options, { value, label: `${value} (previously entered)` }]
    : options;
}
