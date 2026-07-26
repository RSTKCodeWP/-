/**
 * Manages rate profiles with localStorage persistence and history tracking
 */
export class ProfileManager {
  constructor(storage = null) {
    // Use provided storage or default to window.localStorage
    this.storage = storage || (typeof window !== 'undefined' ? window.localStorage : null);
    this.storageKey = 'fpv-rate-profiles';
    this.profiles = this.loadFromStorage();
  }

  /**
   * Load profiles from localStorage
   * @returns {Array} Array of profiles
   */
  loadFromStorage() {
    if (!this.storage) return [];

    try {
      const data = this.storage.getItem(this.storageKey);
      return data ? JSON.parse(data) : [];
    } catch (error) {
      console.error('Failed to load profiles from storage:', error);
      return [];
    }
  }

  /**
   * Save profiles to localStorage
   */
  saveToStorage() {
    if (!this.storage) return;

    try {
      this.storage.setItem(this.storageKey, JSON.stringify(this.profiles));
    } catch (error) {
      console.error('Failed to save profiles to storage:', error);
    }
  }

  /**
   * Create a default profile with standard Betaflight values
   * @param {string} name - Profile name
   * @returns {Object} Default profile
   */
  createDefaultProfile(name = 'Default Profile') {
    return {
      name,
      rates: {
        roll: { center: 70, maxRate: 670, expo: 0 },
        pitch: { center: 70, maxRate: 670, expo: 0 },
        yaw: { center: 70, maxRate: 670, expo: 0 }
      },
      throttle: {
        mid: 50,
        expo: 0
      }
    };
  }

  /**
   * Save a profile to history
   * @param {Object} profile - Profile to save
   * @returns {Object} Saved profile with timestamp
   */
  saveProfile(profile) {
    const profileWithTimestamp = {
      ...profile,
      timestamp: Date.now()
    };

    this.profiles.push(profileWithTimestamp);
    this.saveToStorage();

    return profileWithTimestamp;
  }

  /**
   * Get all saved profiles
   * @returns {Array} Array of profiles
   */
  getProfiles() {
    return [...this.profiles];
  }

  /**
   * Get profile history (alias for getProfiles)
   * @returns {Array} Array of profiles in chronological order
   */
  getHistory() {
    return this.getProfiles();
  }

  /**
   * Delete a profile by timestamp
   * @param {number} timestamp - Profile timestamp
   */
  deleteProfile(timestamp) {
    this.profiles = this.profiles.filter(p => p.timestamp !== timestamp);
    this.saveToStorage();
  }

  /**
   * Export history as JSON string
   * @returns {string} JSON string of all profiles
   */
  exportHistory() {
    return JSON.stringify(this.profiles, null, 2);
  }

  /**
   * Import history from JSON string
   * @param {string} jsonString - JSON string of profiles
   * @param {boolean} merge - If true, merge with existing history. If false, replace.
   */
  importHistory(jsonString, merge = true) {
    try {
      const imported = JSON.parse(jsonString);

      if (!Array.isArray(imported)) {
        throw new Error('Invalid history format: expected array');
      }

      if (merge) {
        this.profiles = [...this.profiles, ...imported];
      } else {
        this.profiles = imported;
      }

      this.saveToStorage();
    } catch (error) {
      console.error('Failed to import history:', error);
      throw error;
    }
  }

  /**
   * Clear all profiles
   */
  clearAll() {
    this.profiles = [];
    this.saveToStorage();
  }
}
