/**
 * Share Link Manager
 * Manages creation and retrieval of share links
 */

import type { ShareLink, ShareConfig, ShareOptions, ShareLinkResponse } from '../types/share';

const API_BASE = '/api/share';

export const shareManager = {
  /**
   * Create a new share link
   */
  async create(config: ShareConfig, options: ShareOptions = {}): Promise<ShareLinkResponse> {
    const response = await fetch(`${API_BASE}/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        config,
        options,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to create share link');
    }

    return response.json();
  },

  /**
   * Get share link by ID
   */
  async get(shortId: string): Promise<ShareLink> {
    const response = await fetch(`${API_BASE}/${shortId}`);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Share link not found');
      }
      if (response.status === 410) {
        throw new Error('Share link has expired');
      }
      throw new Error('Failed to retrieve share link');
    }

    return response.json();
  },

  /**
   * List all share links created by current user
   */
  async list(): Promise<ShareLink[]> {
    const response = await fetch(`${API_BASE}/list`);

    if (!response.ok) {
      throw new Error('Failed to list share links');
    }

    const data = await response.json();
    return data.links || [];
  },

  /**
   * Deactivate a share link
   */
  async deactivate(shortId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/${shortId}/deactivate`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error('Failed to deactivate share link');
    }
  },

  /**
   * Delete a share link
   */
  async delete(shortId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/${shortId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error('Failed to delete share link');
    }
  },

  /**
   * Generate shareable URL
   */
  generateUrl(shortId: string, absolute: boolean = true): string {
    const base = absolute ? window.location.origin : '';
    return `${base}/share/${shortId}`;
  },

  /**
   * Copy share link to clipboard
   */
  async copyToClipboard(url: string): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(url);
      return true;
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
      return false;
    }
  },
};

