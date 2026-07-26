import React from 'react';
import { cn } from '../utils/cn';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular' | 'rounded';
  width?: string | number;
  height?: string | number;
  animation?: 'pulse' | 'wave' | 'none';
}

/**
 * Skeleton Loader Component
 * Provides visual feedback during async operations
 */
export const Skeleton: React.FC<SkeletonProps> = ({
  className,
  variant = 'rectangular',
  width,
  height,
  animation = 'pulse',
}) => {
  const baseClasses = 'bg-gray-200';
  
  const variantClasses = {
    text: 'rounded h-4',
    circular: 'rounded-full',
    rectangular: 'rounded-none',
    rounded: 'rounded-lg',
  };

  const animationClasses = {
    pulse: 'animate-pulse',
    wave: 'animate-wave',
    none: '',
  };

  const style: React.CSSProperties = {
    width: width || '100%',
    height: height || (variant === 'text' ? '1em' : '100%'),
  };

  return (
    <div
      className={cn(
        baseClasses,
        variantClasses[variant],
        animationClasses[animation],
        className
      )}
      style={style}
    />
  );
};

/**
 * Card Skeleton - For loading cards
 */
export const CardSkeleton: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className={cn('bg-white rounded-lg shadow-md p-6 space-y-4', className)}>
      <Skeleton variant="text" width="60%" height={24} />
      <Skeleton variant="text" width="100%" />
      <Skeleton variant="text" width="100%" />
      <Skeleton variant="text" width="80%" />
      <div className="flex gap-2 mt-4">
        <Skeleton variant="rounded" width={100} height={36} />
        <Skeleton variant="rounded" width={100} height={36} />
      </div>
    </div>
  );
};

/**
 * Table Skeleton - For loading tables
 */
export const TableSkeleton: React.FC<{ rows?: number; columns?: number; className?: string }> = ({
  rows = 5,
  columns = 4,
  className,
}) => {
  return (
    <div className={cn('space-y-3', className)}>
      {/* Header */}
      <div className="flex gap-4">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} variant="text" width="100%" height={20} />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton key={colIndex} variant="text" width="100%" height={16} />
          ))}
        </div>
      ))}
    </div>
  );
};

/**
 * Map Skeleton - For loading map views
 */
export const MapSkeleton: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className={cn('relative bg-gray-100 rounded-lg overflow-hidden', className)}>
      <div className="absolute inset-0 bg-gradient-to-br from-gray-200 via-gray-100 to-gray-200 animate-pulse" />
      <div className="absolute top-4 left-4 space-y-2">
        <Skeleton variant="rounded" width={120} height={40} />
        <Skeleton variant="rounded" width={80} height={32} />
      </div>
      <div className="absolute bottom-4 right-4">
        <Skeleton variant="rounded" width={150} height={50} />
      </div>
    </div>
  );
};

/**
 * Avatar Skeleton - For loading user avatars
 */
export const AvatarSkeleton: React.FC<{ size?: number; className?: string }> = ({
  size = 40,
  className,
}) => {
  return (
    <Skeleton
      variant="circular"
      width={size}
      height={size}
      className={className}
    />
  );
};

/**
 * List Skeleton - For loading lists
 */
export const ListSkeleton: React.FC<{ items?: number; className?: string }> = ({
  items = 5,
  className,
}) => {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <AvatarSkeleton size={48} />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" width="70%" />
            <Skeleton variant="text" width="40%" />
          </div>
        </div>
      ))}
    </div>
  );
};

/**
 * Thumbnail Grid Skeleton - For loading image grids
 */
export const ThumbnailGridSkeleton: React.FC<{ count?: number; className?: string }> = ({
  count = 6,
  className,
}) => {
  return (
    <div className={cn('grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton variant="rounded" height={160} />
          <Skeleton variant="text" width="80%" />
          <Skeleton variant="text" width="60%" />
        </div>
      ))}
    </div>
  );
};

export default Skeleton;
