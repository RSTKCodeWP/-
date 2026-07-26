import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Select } from '@/components/ui/select';

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  ChevronDown: (props: any) => <span data-testid="icon-chevron" {...props} />,
  Check: (props: any) => <span data-testid="icon-check" {...props} />,
  Search: (props: any) => <span data-testid="icon-search" {...props} />,
}));

const options = [
  { value: 'stabilize', label: 'Stabilize' },
  { value: 'althold', label: 'Alt Hold' },
  { value: 'loiter', label: 'Loiter' },
  { value: 'auto', label: 'Auto' },
];

describe('Select', () => {
  it('renders with placeholder text', () => {
    render(
      <Select
        options={options}
        value=""
        onChange={vi.fn()}
        placeholder="Choose mode"
      />
    );
    expect(screen.getByText('Choose mode')).toBeDefined();
  });

  it('renders selected option label', () => {
    render(
      <Select
        options={options}
        value="althold"
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Alt Hold')).toBeDefined();
  });

  it('opens dropdown on click', () => {
    render(
      <Select
        options={options}
        value=""
        onChange={vi.fn()}
        placeholder="Choose"
      />
    );

    const trigger = screen.getByRole('combobox');
    fireEvent.click(trigger);

    // All options should be visible in the portal
    expect(screen.getByText('Stabilize')).toBeDefined();
    expect(screen.getByText('Alt Hold')).toBeDefined();
    expect(screen.getByText('Loiter')).toBeDefined();
    expect(screen.getByText('Auto')).toBeDefined();
  });

  it('selects option on click', () => {
    const onChange = vi.fn();
    render(
      <Select
        options={options}
        value=""
        onChange={onChange}
        placeholder="Choose"
      />
    );

    // Open
    fireEvent.click(screen.getByRole('combobox'));
    // Click option
    fireEvent.click(screen.getByText('Loiter'));

    expect(onChange).toHaveBeenCalledWith('loiter');
  });

  it('renders with label', () => {
    render(
      <Select
        label="Flight Mode"
        options={options}
        value=""
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Flight Mode')).toBeDefined();
  });

  it('handles disabled state', () => {
    render(
      <Select
        options={options}
        value=""
        onChange={vi.fn()}
        disabled={true}
        placeholder="Disabled"
      />
    );

    const trigger = screen.getByRole('combobox');
    expect(trigger.hasAttribute('disabled')).toBe(true);
  });

  it('keyboard navigation with ArrowDown and Enter', () => {
    const onChange = vi.fn();
    render(
      <Select
        options={options}
        value=""
        onChange={onChange}
        placeholder="Choose"
      />
    );

    const trigger = screen.getByRole('combobox');

    // ArrowDown opens dropdown
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    expect(screen.getByText('Stabilize')).toBeDefined();

    // ArrowDown moves focus
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    // Enter selects focused option
    fireEvent.keyDown(trigger, { key: 'Enter' });

    expect(onChange).toHaveBeenCalledWith('stabilize');
  });

  it('Escape closes dropdown', () => {
    render(
      <Select
        options={options}
        value=""
        onChange={vi.fn()}
        placeholder="Choose"
      />
    );

    const trigger = screen.getByRole('combobox');
    fireEvent.click(trigger);
    expect(screen.getByText('Stabilize')).toBeDefined();

    fireEvent.keyDown(trigger, { key: 'Escape' });
    // Dropdown should close; options should not be in listbox role
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('searchable mode shows search input', () => {
    render(
      <Select
        options={options}
        value=""
        onChange={vi.fn()}
        searchable={true}
        searchPlaceholder="Filter modes"
      />
    );

    fireEvent.click(screen.getByRole('combobox'));
    expect(screen.getByPlaceholderText('Filter modes')).toBeDefined();
  });

  it('shows option description when provided', () => {
    const optionsWithDesc = [
      { value: 'stabilize', label: 'Stabilize', description: 'Manual with self-level' },
      { value: 'auto', label: 'Auto', description: 'Autonomous mission' },
    ];

    render(
      <Select
        options={optionsWithDesc}
        value=""
        onChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('combobox'));
    expect(screen.getByText('Manual with self-level')).toBeDefined();
    expect(screen.getByText('Autonomous mission')).toBeDefined();
  });

  it('handles grouped options', () => {
    const groupedOptions = [
      {
        label: 'Flight',
        options: [
          { value: 'stabilize', label: 'Stabilize' },
          { value: 'althold', label: 'Alt Hold' },
        ],
      },
      {
        label: 'Auto',
        options: [
          { value: 'auto', label: 'Auto' },
          { value: 'rtl', label: 'RTL' },
        ],
      },
    ];

    render(
      <Select
        options={groupedOptions}
        value=""
        onChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('combobox'));
    expect(screen.getByText('Flight')).toBeDefined();
    // "Auto" appears as both group header and option label, so use getAllByText
    expect(screen.getAllByText('Auto').length).toBeGreaterThanOrEqual(1);
  });
});
