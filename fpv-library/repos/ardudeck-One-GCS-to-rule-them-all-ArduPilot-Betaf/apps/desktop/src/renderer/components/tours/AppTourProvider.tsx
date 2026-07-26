import type { ReactNode } from 'react';
import { TourManager } from './TourManager';

interface AppTourProviderProps {
  children: ReactNode;
}

export function AppTourProvider({ children }: AppTourProviderProps) {
  return (
    <>
      {children}
      <TourManager />
    </>
  );
}
