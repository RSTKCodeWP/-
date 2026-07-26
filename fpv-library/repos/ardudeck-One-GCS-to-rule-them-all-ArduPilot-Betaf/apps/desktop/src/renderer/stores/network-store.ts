import { create } from 'zustand';

interface NetworkState {
  isOnline: boolean;
}

export const useNetworkStore = create<NetworkState>(() => ({
  isOnline: navigator.onLine,
}));

// Listen to browser online/offline events
window.addEventListener('online', () => useNetworkStore.setState({ isOnline: true }));
window.addEventListener('offline', () => useNetworkStore.setState({ isOnline: false }));
