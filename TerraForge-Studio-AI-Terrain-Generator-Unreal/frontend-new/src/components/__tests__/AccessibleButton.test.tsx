import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AccessibleButton } from '../AccessibleButton';
import { Save } from 'lucide-react';

describe('AccessibleButton', () => {
  it('renders with children', () => {
    render(<AccessibleButton>Click me</AccessibleButton>);
    expect(screen.getByRole('button', { name: /Click me/i })).toBeInTheDocument();
  });

  it('applies correct variant classes', () => {
    const { rerender } = render(
      <AccessibleButton variant="primary">Primary</AccessibleButton>
    );
    let button = screen.getByRole('button');
    expect(button).toHaveClass('bg-blue-600');

    rerender(<AccessibleButton variant="danger">Danger</AccessibleButton>);
    button = screen.getByRole('button');
    expect(button).toHaveClass('bg-red-600');
  });

  it('applies correct size classes', () => {
    const { rerender } = render(
      <AccessibleButton size="sm">Small</AccessibleButton>
    );
    let button = screen.getByRole('button');
    expect(button).toHaveClass('px-3', 'py-1.5');

    rerender(<AccessibleButton size="lg">Large</AccessibleButton>);
    button = screen.getByRole('button');
    expect(button).toHaveClass('px-6', 'py-3');
  });

  it('shows loading state', () => {
    render(<AccessibleButton isLoading>Loading</AccessibleButton>);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
  });

  it('is disabled when disabled prop is true', () => {
    render(<AccessibleButton disabled>Disabled</AccessibleButton>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when loading', () => {
    render(<AccessibleButton isLoading>Loading</AccessibleButton>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('calls onClick handler', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();

    render(<AccessibleButton onClick={handleClick}>Click</AccessibleButton>);
    
    await user.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders with left and right icons', () => {
    render(
      <AccessibleButton 
        leftIcon={<Save data-testid="left-icon" />}
        rightIcon={<Save data-testid="right-icon" />}
      >
        With Icons
      </AccessibleButton>
    );

    expect(screen.getByTestId('left-icon')).toBeInTheDocument();
    expect(screen.getByTestId('right-icon')).toBeInTheDocument();
  });

  it('has proper ARIA attributes', () => {
    render(<AccessibleButton disabled>Button</AccessibleButton>);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-disabled', 'true');
  });

  it('is keyboard accessible', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();

    render(<AccessibleButton onClick={handleClick}>Button</AccessibleButton>);
    
    const button = screen.getByRole('button');
    button.focus();
    expect(button).toHaveFocus();

    await user.keyboard('{Enter}');
    expect(handleClick).toHaveBeenCalled();
  });
});
