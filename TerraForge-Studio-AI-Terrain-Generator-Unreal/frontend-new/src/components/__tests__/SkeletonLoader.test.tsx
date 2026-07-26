import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { 
  Skeleton, 
  CardSkeleton, 
  TableSkeleton,
  ListSkeleton,
  ThumbnailGridSkeleton,
  MapSkeleton,
  AvatarSkeleton
} from '../SkeletonLoader';

describe('Skeleton Components', () => {
  describe('Skeleton', () => {
    it('renders with default props', () => {
      const { container } = render(<Skeleton />);
      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton).toHaveClass('bg-gray-200', 'animate-pulse');
    });

    it('applies variant classes correctly', () => {
      const { container, rerender } = render(<Skeleton variant="text" />);
      let skeleton = container.firstChild as HTMLElement;
      expect(skeleton).toHaveClass('rounded', 'h-4');

      rerender(<Skeleton variant="circular" />);
      skeleton = container.firstChild as HTMLElement;
      expect(skeleton).toHaveClass('rounded-full');

      rerender(<Skeleton variant="rounded" />);
      skeleton = container.firstChild as HTMLElement;
      expect(skeleton).toHaveClass('rounded-lg');
    });

    it('applies custom width and height', () => {
      const { container } = render(<Skeleton width={200} height={100} />);
      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton).toHaveStyle({ width: '200px', height: '100px' });
    });

    it('applies animation classes', () => {
      const { container, rerender } = render(<Skeleton animation="pulse" />);
      let skeleton = container.firstChild as HTMLElement;
      expect(skeleton).toHaveClass('animate-pulse');

      rerender(<Skeleton animation="none" />);
      skeleton = container.firstChild as HTMLElement;
      expect(skeleton).not.toHaveClass('animate-pulse');
    });
  });

  describe('CardSkeleton', () => {
    it('renders card structure', () => {
      const { container } = render(<CardSkeleton />);
      expect(container.querySelector('.bg-white.rounded-lg')).toBeInTheDocument();
    });
  });

  describe('TableSkeleton', () => {
    it('renders correct number of rows', () => {
      const { container } = render(<TableSkeleton rows={3} columns={4} />);
      // 3 rows + 1 header = 4 total
      const rows = container.querySelectorAll('.flex.gap-4');
      expect(rows).toHaveLength(4);
    });
  });

  describe('ListSkeleton', () => {
    it('renders correct number of items', () => {
      const { container } = render(<ListSkeleton items={5} />);
      const items = container.querySelectorAll('.flex.items-center');
      expect(items).toHaveLength(5);
    });
  });

  describe('ThumbnailGridSkeleton', () => {
    it('renders correct number of thumbnails', () => {
      const { container } = render(<ThumbnailGridSkeleton count={6} />);
      const items = container.querySelectorAll('.space-y-2');
      expect(items).toHaveLength(6);
    });
  });

  describe('MapSkeleton', () => {
    it('renders map skeleton structure', () => {
      const { container } = render(<MapSkeleton />);
      expect(container.querySelector('.bg-gray-100.rounded-lg')).toBeInTheDocument();
    });
  });

  describe('AvatarSkeleton', () => {
    it('renders with correct size', () => {
      const { container } = render(<AvatarSkeleton size={64} />);
      const avatar = container.firstChild as HTMLElement;
      expect(avatar).toHaveStyle({ width: '64px', height: '64px' });
    });
  });
});
