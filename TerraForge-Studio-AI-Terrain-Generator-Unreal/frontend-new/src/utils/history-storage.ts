/**
 * Generation History Storage Utilities
 * Manages persistent storage of terrain generation history
 */

import type { GenerationHistoryItem } from '../types/history';

const STORAGE_KEY = 'terraforge-generation-history';
const MAX_HISTORY_ITEMS = 100; // Keep last 100 generations

export const historyStorage = {
  /**
   * Get all history items
   */
  getAll(): GenerationHistoryItem[] {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (!data) return [];
      return JSON.parse(data) as GenerationHistoryItem[];
    } catch (error) {
      console.error('Failed to load history:', error);
      return [];
    }
  },

  /**
   * Add a new history item
   */
  add(item: GenerationHistoryItem): void {
    try {
      const history = this.getAll();
      history.unshift(item); // Add to beginning
      
      // Keep only MAX_HISTORY_ITEMS
      const trimmed = history.slice(0, MAX_HISTORY_ITEMS);
      
      localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    } catch (error) {
      console.error('Failed to save history item:', error);
    }
  },

  /**
   * Update an existing history item
   */
  update(id: string, updates: Partial<GenerationHistoryItem>): void {
    try {
      const history = this.getAll();
      const index = history.findIndex(item => item.id === id);
      
      if (index !== -1) {
        history[index] = { ...history[index], ...updates };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
      }
    } catch (error) {
      console.error('Failed to update history item:', error);
    }
  },

  /**
   * Delete a history item
   */
  delete(id: string): void {
    try {
      const history = this.getAll();
      const filtered = history.filter(item => item.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    } catch (error) {
      console.error('Failed to delete history item:', error);
    }
  },

  /**
   * Clear all history
   */
  clearAll(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  },

  /**
   * Get history item by ID
   */
  getById(id: string): GenerationHistoryItem | null {
    const history = this.getAll();
    return history.find(item => item.id === id) || null;
  },

  /**
   * Search history items
   */
  search(query: string): GenerationHistoryItem[] {
    const history = this.getAll();
    const lowerQuery = query.toLowerCase();
    
    return history.filter(item =>
      item.name.toLowerCase().includes(lowerQuery) ||
      item.config.exportFormats.some(fmt => fmt.toLowerCase().includes(lowerQuery))
    );
  },

  /**
   * Get statistics
   */
  getStats() {
    const history = this.getAll();
    return {
      total: history.length,
      completed: history.filter(h => h.status === 'completed').length,
      failed: history.filter(h => h.status === 'failed').length,
      totalDuration: history.reduce((sum, h) => sum + (h.stats?.duration || 0), 0),
      totalSize: history.reduce((sum, h) => sum + (h.stats?.fileSize || 0), 0),
    };
  },
};

