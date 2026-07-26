import { GraphRenderer } from './graph-renderer.js';
import { ProfileManager } from './profile-manager.js';
import { parseCLI, generateCLI } from './cli-parser.js';
import { normalizeLimitPercent, normalizeLimitType } from './rate-calculator.js';

/**
 * Main application controller
 */
class RateProfileComparison {
  constructor() {
    // Initialize components
    this.profileManager = new ProfileManager();
    this.graphRenderer = new GraphRenderer(
      document.getElementById('rate-canvas'),
      document.getElementById('throttle-canvas')
    );

    // Side-by-side renderers (created lazily)
    this.graphRendererA = null;
    this.graphRendererB = null;

    // View mode
    this.viewMode = 'overlay'; // 'overlay' or 'sidebyside'
    this.minWidthForSideBySide = 1400;

    // Current profiles
    this.profileA = this.createDefaultProfile('Profile A');
    this.profileB = this.createDefaultProfile('Profile B');

    // Auto-save debounce timer
    this.autoSaveTimer = null;
    this.autoSaveDelay = 2000; // 2 seconds

    // Initialize UI
    this.initializeControls();
    this.initializeVisibilityToggles();
    this.initializeViewMode();
    this.initializeImportExport();
    this.initializeProfileActions();
    this.initializeHistory();
    this.initializeGraphCollapse();

    // Check viewport width and update view mode controls
    this.checkViewportWidth();
    window.addEventListener('resize', () => this.checkViewportWidth());

    // Initial render
    this.updateGraphs();
    this.updateExports();
    this.renderHistory();
  }

  createDefaultProfile(name) {
    return {
      name,
      rates: {
        roll: { center: 70, maxRate: 670, expo: 0 },
        pitch: { center: 70, maxRate: 670, expo: 0 },
        yaw: { center: 70, maxRate: 670, expo: 0 }
      },
      throttle: {
        mid: 50,
        expo: 0,
        limitType: 'OFF',
        limitPercent: 100
      }
    };
  }

  initializeControls() {
    const profiles = ['a', 'b'];
    const axes = ['roll', 'pitch', 'yaw'];

    profiles.forEach(profile => {
      const profileObj = profile === 'a' ? this.profileA : this.profileB;

      // Rate controls
      axes.forEach(axis => {
        // Center
        const centerInput = document.getElementById(`${profile}-${axis}-center`);
        const centerValue = document.getElementById(`${profile}-${axis}-center-value`);
        centerInput.addEventListener('input', (e) => {
          const value = parseInt(e.target.value);
          profileObj.rates[axis].center = value;
          centerValue.textContent = value;
          this.onProfileChange();
        });

        // Max Rate
        const maxInput = document.getElementById(`${profile}-${axis}-max`);
        const maxValue = document.getElementById(`${profile}-${axis}-max-value`);
        maxInput.addEventListener('input', (e) => {
          const value = parseInt(e.target.value);
          profileObj.rates[axis].maxRate = value;
          maxValue.textContent = value;
          this.onProfileChange();
        });

        // Expo
        const expoInput = document.getElementById(`${profile}-${axis}-expo`);
        const expoValue = document.getElementById(`${profile}-${axis}-expo-value`);
        expoInput.addEventListener('input', (e) => {
          const value = parseInt(e.target.value);
          profileObj.rates[axis].expo = value;
          expoValue.textContent = value;
          this.onProfileChange();
        });
      });

      // Throttle controls
      const throttleMidInput = document.getElementById(`${profile}-throttle-mid`);
      const throttleMidValue = document.getElementById(`${profile}-throttle-mid-value`);
      throttleMidInput.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        profileObj.throttle.mid = value;
        throttleMidValue.textContent = value;
        this.onProfileChange();
      });

      const throttleExpoInput = document.getElementById(`${profile}-throttle-expo`);
      const throttleExpoValue = document.getElementById(`${profile}-throttle-expo-value`);
      throttleExpoInput.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        profileObj.throttle.expo = value;
        throttleExpoValue.textContent = value;
        this.onProfileChange();
      });

      const throttleLimitTypeInput = document.getElementById(`${profile}-throttle-limit-type`);
      throttleLimitTypeInput.addEventListener('change', (e) => {
        profileObj.throttle.limitType = e.target.value;
        this.onProfileChange();
      });

      const throttleLimitPercentInput = document.getElementById(`${profile}-throttle-limit-percent`);
      const throttleLimitPercentValue = document.getElementById(`${profile}-throttle-limit-percent-value`);
      throttleLimitPercentInput.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        profileObj.throttle.limitPercent = value;
        throttleLimitPercentValue.textContent = value;
        this.onProfileChange();
      });
    });
  }

  initializeVisibilityToggles() {
    document.getElementById('toggle-profile-a').addEventListener('change', (e) => {
      this.graphRenderer.setVisibility({ profileA: e.target.checked });
      this.updateGraphs();
    });

    document.getElementById('toggle-profile-b').addEventListener('change', (e) => {
      this.graphRenderer.setVisibility({ profileB: e.target.checked });
      this.updateGraphs();
    });

    document.getElementById('toggle-roll').addEventListener('change', (e) => {
      this.graphRenderer.setVisibility({ roll: e.target.checked });
      this.updateGraphs();
    });

    document.getElementById('toggle-pitch').addEventListener('change', (e) => {
      this.graphRenderer.setVisibility({ pitch: e.target.checked });
      this.updateGraphs();
    });

    document.getElementById('toggle-yaw').addEventListener('change', (e) => {
      this.graphRenderer.setVisibility({ yaw: e.target.checked });
      this.updateGraphs();
    });
  }

  initializeViewMode() {
    document.getElementById('view-mode-overlay').addEventListener('change', (e) => {
      if (e.target.checked) {
        this.setViewMode('overlay');
      }
    });

    document.getElementById('view-mode-sidebyside').addEventListener('change', (e) => {
      if (e.target.checked) {
        this.setViewMode('sidebyside');
      }
    });
  }

  checkViewportWidth() {
    const width = window.innerWidth;
    const viewModeControl = document.getElementById('view-mode-control');

    if (width >= this.minWidthForSideBySide) {
      // Show view mode toggle on wide screens
      viewModeControl.style.display = '';
    } else {
      // Hide on narrow screens and force overlay mode
      viewModeControl.style.display = 'none';
      if (this.viewMode === 'sidebyside') {
        document.getElementById('view-mode-overlay').checked = true;
        this.setViewMode('overlay');
      }
    }
  }

  setViewMode(mode) {
    this.viewMode = mode;
    const overlayContainer = document.getElementById('graphs-overlay');
    const sideBySideContainer = document.getElementById('graphs-sidebyside');

    if (mode === 'overlay') {
      overlayContainer.style.display = '';
      sideBySideContainer.style.display = 'none';
    } else {
      overlayContainer.style.display = 'none';
      sideBySideContainer.style.display = '';

      // Initialize side-by-side renderers if not already done
      if (!this.graphRendererA) {
        this.graphRendererA = new GraphRenderer(
          document.getElementById('rate-canvas-a'),
          document.getElementById('throttle-canvas-a')
        );
      }
      if (!this.graphRendererB) {
        this.graphRendererB = new GraphRenderer(
          document.getElementById('rate-canvas-b'),
          document.getElementById('throttle-canvas-b')
        );
      }
    }

    this.updateGraphs();
  }

  initializeImportExport() {
    // Profile A
    document.getElementById('import-btn-a').addEventListener('click', () => {
      this.importProfile('a');
    });

    document.getElementById('copy-btn-a').addEventListener('click', () => {
      this.copyExport('a');
    });

    // Profile B
    document.getElementById('import-btn-b').addEventListener('click', () => {
      this.importProfile('b');
    });

    document.getElementById('copy-btn-b').addEventListener('click', () => {
      this.copyExport('b');
    });
  }

  initializeProfileActions() {
    // Save Profile A
    document.getElementById('save-profile-a').addEventListener('click', () => {
      this.saveProfile('a');
    });

    // Save Profile B
    document.getElementById('save-profile-b').addEventListener('click', () => {
      this.saveProfile('b');
    });

    // Profile name inputs
    document.getElementById('profile-a-name').addEventListener('input', (e) => {
      this.profileA.name = e.target.value || 'Profile A';
      this.updateExports();
    });

    document.getElementById('profile-b-name').addEventListener('input', (e) => {
      this.profileB.name = e.target.value || 'Profile B';
      this.updateExports();
    });
  }

  initializeHistory() {
    document.getElementById('export-history-btn').addEventListener('click', () => {
      this.exportHistory();
    });

    document.getElementById('import-history-btn').addEventListener('click', () => {
      document.getElementById('history-file-input').click();
    });

    document.getElementById('history-file-input').addEventListener('change', (e) => {
      this.importHistoryFromFile(e.target.files[0]);
    });

    document.getElementById('clear-history-btn').addEventListener('click', () => {
      if (confirm('Are you sure you want to clear all history? This cannot be undone.')) {
        this.profileManager.clearAll();
        this.renderHistory();
      }
    });
  }

  initializeGraphCollapse() {
    this.collapseStorageKey = 'fpv-rate-graph-collapsed';
    const stored = this.loadCollapsedState();

    document.querySelectorAll('.graph-panel[data-collapse-key]').forEach(panel => {
      const key = panel.dataset.collapseKey;
      if (stored[key]) {
        panel.classList.add('collapsed');
      }
      const header = panel.querySelector('.graph-panel-header');
      if (!header) return;
      header.setAttribute('aria-expanded', String(!panel.classList.contains('collapsed')));
      header.addEventListener('click', () => {
        const collapsed = panel.classList.toggle('collapsed');
        header.setAttribute('aria-expanded', String(!collapsed));
        this.saveCollapsedState(key, collapsed);
        // Re-render so the canvas is correctly sized after expanding
        if (!collapsed) this.updateGraphs();
      });
    });
  }

  loadCollapsedState() {
    try {
      const raw = localStorage.getItem(this.collapseStorageKey);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed;
      }
      return {};
    } catch {
      return {};
    }
  }

  saveCollapsedState(key, collapsed) {
    try {
      const state = this.loadCollapsedState();
      if (collapsed) {
        state[key] = true;
      } else {
        delete state[key];
      }
      localStorage.setItem(this.collapseStorageKey, JSON.stringify(state));
    } catch {
      // Ignore quota / privacy-mode errors
    }
  }

  onProfileChange() {
    // Update graphs immediately
    this.updateGraphs();
    this.updateExports();

    // Debounced auto-save
    clearTimeout(this.autoSaveTimer);
    this.autoSaveTimer = setTimeout(() => {
      // Auto-save only if profile has a custom name
      if (this.profileA.name && this.profileA.name !== 'Profile A') {
        this.profileManager.saveProfile({ ...this.profileA });
      }
      if (this.profileB.name && this.profileB.name !== 'Profile B') {
        this.profileManager.saveProfile({ ...this.profileB });
      }
      this.renderHistory();
    }, this.autoSaveDelay);
  }

  updateGraphs() {
    if (this.viewMode === 'overlay') {
      this.graphRenderer.render(this.profileA, this.profileB);
    } else {
      // Side-by-side mode - render each profile separately
      if (this.graphRendererA && this.graphRendererB) {
        // For side-by-side, we show each profile independently (not overlaid)
        // So we pass the profile and null for the second profile
        this.graphRendererA.render(this.profileA, null);
        this.graphRendererB.render(this.profileB, null);
      }
    }
  }

  updateExports() {
    document.getElementById('export-a').value = generateCLI(this.profileA);
    document.getElementById('export-b').value = generateCLI(this.profileB);
  }

  importProfile(profile) {
    const textarea = document.getElementById(`import-${profile}`);
    const statusSpan = document.getElementById(`import-status-${profile}`);
    const text = textarea.value;

    if (!text.trim()) {
      this.showStatus(statusSpan, 'Please paste CLI dump text first.', 'error');
      return;
    }

    try {
      const settings = parseCLI(text);
      const profileObj = profile === 'a' ? this.profileA : this.profileB;

      // Map settings to profile
      const mapping = {
        roll_rc_rate: (v) => profileObj.rates.roll.center = parseInt(v),
        pitch_rc_rate: (v) => profileObj.rates.pitch.center = parseInt(v),
        yaw_rc_rate: (v) => profileObj.rates.yaw.center = parseInt(v),
        roll_rate: (v) => profileObj.rates.roll.maxRate = parseInt(v),
        pitch_rate: (v) => profileObj.rates.pitch.maxRate = parseInt(v),
        yaw_rate: (v) => profileObj.rates.yaw.maxRate = parseInt(v),
        roll_expo: (v) => profileObj.rates.roll.expo = parseInt(v),
        pitch_expo: (v) => profileObj.rates.pitch.expo = parseInt(v),
        yaw_expo: (v) => profileObj.rates.yaw.expo = parseInt(v),
        thr_mid: (v) => profileObj.throttle.mid = parseInt(v),
        thr_expo: (v) => profileObj.throttle.expo = parseInt(v),
        throttle_limit_type: (v) => profileObj.throttle.limitType = normalizeLimitType(v),
        throttle_limit_percent: (v) => profileObj.throttle.limitPercent = normalizeLimitPercent(v)
      };

      let count = 0;
      for (const [key, handler] of Object.entries(mapping)) {
        if (settings[key] !== undefined) {
          handler(settings[key]);
          count++;
        }
      }

      // Update UI
      this.updateUIFromProfile(profile, profileObj);
      this.updateGraphs();
      this.updateExports();

      this.showStatus(statusSpan, `Successfully imported ${count} settings`, 'success');
      textarea.value = '';
    } catch (error) {
      this.showStatus(statusSpan, `Import failed: ${error.message}`, 'error');
    }
  }

  updateUIFromProfile(profile, profileObj) {
    const axes = ['roll', 'pitch', 'yaw'];

    axes.forEach(axis => {
      // Center
      document.getElementById(`${profile}-${axis}-center`).value = profileObj.rates[axis].center;
      document.getElementById(`${profile}-${axis}-center-value`).textContent = profileObj.rates[axis].center;

      // Max Rate
      document.getElementById(`${profile}-${axis}-max`).value = profileObj.rates[axis].maxRate;
      document.getElementById(`${profile}-${axis}-max-value`).textContent = profileObj.rates[axis].maxRate;

      // Expo
      document.getElementById(`${profile}-${axis}-expo`).value = profileObj.rates[axis].expo;
      document.getElementById(`${profile}-${axis}-expo-value`).textContent = profileObj.rates[axis].expo;
    });

    // Throttle
    document.getElementById(`${profile}-throttle-mid`).value = profileObj.throttle.mid;
    document.getElementById(`${profile}-throttle-mid-value`).textContent = profileObj.throttle.mid;
    document.getElementById(`${profile}-throttle-expo`).value = profileObj.throttle.expo;
    document.getElementById(`${profile}-throttle-expo-value`).textContent = profileObj.throttle.expo;
    document.getElementById(`${profile}-throttle-limit-type`).value = profileObj.throttle.limitType ?? 'OFF';
    const limitPercent = profileObj.throttle.limitPercent ?? 100;
    document.getElementById(`${profile}-throttle-limit-percent`).value = limitPercent;
    document.getElementById(`${profile}-throttle-limit-percent-value`).textContent = limitPercent;
  }

  async copyExport(profile) {
    const textarea = document.getElementById(`export-${profile}`);
    const statusSpan = document.getElementById(`export-status-${profile}`);

    try {
      await navigator.clipboard.writeText(textarea.value);
      this.showStatus(statusSpan, 'Copied to clipboard!', 'success');
    } catch (error) {
      // Fallback
      textarea.select();
      document.execCommand('copy');
      this.showStatus(statusSpan, 'Copied to clipboard!', 'success');
    }
  }

  saveProfile(profile) {
    const profileObj = profile === 'a' ? this.profileA : this.profileB;
    const nameInput = document.getElementById(`profile-${profile}-name`);

    if (!nameInput.value.trim()) {
      alert('Please enter a profile name before saving.');
      nameInput.focus();
      return;
    }

    profileObj.name = nameInput.value;
    this.profileManager.saveProfile({ ...profileObj });
    this.renderHistory();

    // Show feedback
    const statusSpan = document.getElementById(`export-status-${profile}`);
    this.showStatus(statusSpan, `Profile saved: ${profileObj.name}`, 'success');
  }

  renderHistory() {
    const historyList = document.getElementById('history-list');
    const history = this.profileManager.getHistory();

    if (history.length === 0) {
      historyList.innerHTML = '<p class="empty-history">No saved profiles yet. Save a profile to start building your history.</p>';
      return;
    }

    historyList.innerHTML = history.map((profile, index) => `
      <div class="history-item" data-index="${index}">
        <div class="history-item-header">
          <h4>${this.escapeHtml(profile.name)}</h4>
          <span class="history-timestamp">${new Date(profile.timestamp).toLocaleString()}</span>
        </div>
        <div class="history-item-actions">
          <button class="btn btn-small load-to-a" data-timestamp="${profile.timestamp}">Load to A</button>
          <button class="btn btn-small load-to-b" data-timestamp="${profile.timestamp}">Load to B</button>
          <button class="btn btn-small btn-danger delete-profile" data-timestamp="${profile.timestamp}">Delete</button>
        </div>
      </div>
    `).join('');

    // Add event listeners
    historyList.querySelectorAll('.load-to-a').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const timestamp = parseInt(e.target.dataset.timestamp);
        this.loadProfileTo('a', timestamp);
      });
    });

    historyList.querySelectorAll('.load-to-b').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const timestamp = parseInt(e.target.dataset.timestamp);
        this.loadProfileTo('b', timestamp);
      });
    });

    historyList.querySelectorAll('.delete-profile').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const timestamp = parseInt(e.target.dataset.timestamp);
        if (confirm('Delete this profile from history?')) {
          this.profileManager.deleteProfile(timestamp);
          this.renderHistory();
        }
      });
    });
  }

  loadProfileTo(target, timestamp) {
    const history = this.profileManager.getHistory();
    const profile = history.find(p => p.timestamp === timestamp);

    if (!profile) return;

    if (target === 'a') {
      this.profileA = { ...profile };
      this.updateUIFromProfile('a', this.profileA);
      document.getElementById('profile-a-name').value = profile.name;
    } else {
      this.profileB = { ...profile };
      this.updateUIFromProfile('b', this.profileB);
      document.getElementById('profile-b-name').value = profile.name;
    }

    this.updateGraphs();
    this.updateExports();
  }

  exportHistory() {
    const json = this.profileManager.exportHistory();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fpv-rate-profiles-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  importHistoryFromFile(file) {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        this.profileManager.importHistory(e.target.result);
        this.renderHistory();
        alert('History imported successfully!');
      } catch (error) {
        alert(`Import failed: ${error.message}`);
      }
    };
    reader.readAsText(file);
  }

  showStatus(element, message, type) {
    element.textContent = message;
    element.className = `status-message ${type}`;
    setTimeout(() => {
      element.textContent = '';
      element.className = 'status-message';
    }, 3000);
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new RateProfileComparison();
});
