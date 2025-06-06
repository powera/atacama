// Access React hooks from the global React object
const { useState, useEffect, useRef, useCallback } = React;

/**
 * Default settings configuration
 */
const DEFAULT_SETTINGS = {
  // Audio & Feedback
  audioEnabled: true,
  soundVolume: 0.7, // 0-1 range
  hapticFeedback: true, // For mobile devices
  
  // Difficulty & Learning
  difficulty: 'medium', // 'easy', 'medium', 'hard'
  adaptiveDifficulty: true, // Auto-adjust based on performance
  hintsEnabled: true,
  
  // Personalization
  userName: '',
  preferredLanguage: 'en', // For multi-language widgets
  
  // Visual & Animations
  animations: true,
  reducedMotion: false, // Accessibility: honor prefers-reduced-motion
  theme: 'auto', // 'auto', 'light', 'dark', 'high-contrast'
  fontSize: 'medium', // 'small', 'medium', 'large'
  
  // Timing & Flow
  autoAdvance: false,
  defaultDelay: 2.5, // seconds, range 1.0 to 7.5
  
  // Privacy & Data
  anonymousMode: false, // Don't track any progress/stats
  shareProgress: true, // Allow sharing achievements
  
  // Accessibility
  keyboardShortcuts: true,
  screenReaderMode: false,
  highContrastMode: false
};

/**
 * Settings storage key for localStorage
 */
const SETTINGS_STORAGE_KEY = 'atacama_global_settings';

/**
 * Load settings from localStorage with fallback to defaults
 */
const loadSettings = () => {
  try {
    const stored = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      // Merge with defaults to handle new settings
      return { ...DEFAULT_SETTINGS, ...parsed };
    }
  } catch (error) {
    console.warn('Failed to load settings from localStorage:', error);
  }
  return { ...DEFAULT_SETTINGS };
};

/**
 * Save settings to localStorage
 */
const saveSettings = (settings) => {
  try {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
  } catch (error) {
    console.warn('Failed to save settings to localStorage:', error);
  }
};

/**
 * Custom hook for global settings management
 * 
 * @param {Object} options - Configuration options
 * @param {Array<string>} options.usedSettings - Array of setting keys that should be shown on the first page
 * 
 * @returns {Object} Object containing:
 *   - settings: current settings object
 *   - updateSetting: function to update a single setting
 *   - updateSettings: function to update multiple settings at once
 *   - resetSettings: function to reset all settings to defaults
 *   - showGlobalSettings: boolean indicating if settings modal is open
 *   - toggleGlobalSettings: function to toggle settings modal
 *   - readGlobalSettings: function to get current settings (for compatibility)
 *   - SettingsModal: React component for the settings modal
 *   - SettingsToggle: React component for the settings toggle button
 * 
 * @example
 * const MyWidget = () => {
 *   const { 
 *     settings, 
 *     updateSetting, 
 *     SettingsModal,
 *     SettingsToggle
 *   } = useGlobalSettings({
 *     usedSettings: ['audioEnabled', 'difficulty', 'autoAdvance']
 *   });
 *   
 *   return (
 *     <div>
 *       <SettingsToggle />
 *       {settings.audioEnabled && <audio autoPlay />}
 *       <div className={`difficulty-${settings.difficulty}`}>
 *         Game content here...
 *       </div>
 *       <SettingsModal />
 *     </div>
 *   );
 * };
 */
export const useGlobalSettings = (options = {}) => {
  const { usedSettings = [] } = options;
  const [settings, setSettings] = useState(loadSettings);
  const [showGlobalSettings, setShowGlobalSettings] = useState(false);
  const [activeTab, setActiveTab] = useState(usedSettings.length > 0 ? 'used' : 'general');
  const modalRef = useRef(null);
  const scrollPositionRef = useRef(0);

  // Save settings whenever they change, but debounce to avoid excessive saves
  const debouncedSaveSettings = useCallback(
    (() => {
      let timeoutId = null;
      return (newSettings) => {
        if (timeoutId) clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
          saveSettings(newSettings);
        }, 100);
      };
    })(),
    []
  );

  useEffect(() => {
    debouncedSaveSettings(settings);
  }, [settings, debouncedSaveSettings]);

  // Check for system preferences on mount
  useEffect(() => {
    if (window.matchMedia) {
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      
      setSettings(prev => ({
        ...prev,
        reducedMotion: prev.reducedMotion || prefersReducedMotion,
        theme: prev.theme === 'auto' ? (prefersDark ? 'dark' : 'light') : prev.theme
      }));
    }
  }, []);

  // Memoized update function to prevent unnecessary re-renders
  const updateSetting = useCallback((key, value) => {
    // Store current scroll position of the modal if it exists
    if (modalRef.current) {
      scrollPositionRef.current = modalRef.current.scrollTop;
    }
    
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  }, []);

  // Update multiple settings at once
  const updateSettings = useCallback((updates) => {
    if (modalRef.current) {
      scrollPositionRef.current = modalRef.current.scrollTop;
    }
    
    setSettings(prev => ({
      ...prev,
      ...updates
    }));
  }, []);

  // Restore scroll position after settings update
  useEffect(() => {
    if (scrollPositionRef.current > 0 && modalRef.current) {
      // Use requestAnimationFrame to ensure DOM has updated
      requestAnimationFrame(() => {
        modalRef.current.scrollTop = scrollPositionRef.current;
      });
    }
  }, [settings]);

  const resetSettings = useCallback(() => {
    // Store current scroll position of the modal if it exists
    if (modalRef.current) {
      scrollPositionRef.current = modalRef.current.scrollTop;
    }
    setSettings({ ...DEFAULT_SETTINGS });
  }, []);

  const toggleGlobalSettings = useCallback(() => {
    setShowGlobalSettings(prev => {
      // Reset scroll position reference when opening or closing
      scrollPositionRef.current = 0;
      return !prev;
    });
  }, []);

  const readGlobalSettings = useCallback(() => {
    return { ...settings };
  }, [settings]);

  // Handle escape key and outside clicks
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && showGlobalSettings) {
        setShowGlobalSettings(false);
      }
    };

    const handleClickOutside = (event) => {
      // Check if modalRef and modalRef.current exist before calling contains
      if (modalRef.current && event.target && !modalRef.current.contains(event.target)) {
        setShowGlobalSettings(false);
      }
    };

    if (showGlobalSettings) {
      document.addEventListener('keydown', handleKeyDown);
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showGlobalSettings]);

  /**
   * Settings Toggle Button Component
   */
  const SettingsToggle = useCallback(({ children, ...props }) => {
    return (
      <button
        onClick={toggleGlobalSettings}
        className="w-settings-toggle"
        aria-label="Open global settings"
        {...props}
      >
        <span className="w-settings-icon">⚙️</span>
        {children || 'Settings'}
      </button>
    );
  }, [toggleGlobalSettings]);

  /**
   * Helper function to render individual setting components
   */
  const renderSetting = (settingKey) => {
    switch (settingKey) {
      case 'userName':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-label">Your Name</label>
            <input
              type="text"
              value={settings.userName}
              onChange={(e) => updateSetting('userName', e.target.value)}
              placeholder="Enter your name (optional)"
              className="w-setting-input"
            />
            <p className="w-setting-description">
              Personalize your experience with widgets
            </p>
          </div>
        );

      case 'difficulty':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-label">Default Difficulty</label>
            <select
              value={settings.difficulty}
              onChange={(e) => updateSetting('difficulty', e.target.value)}
              className="w-setting-select"
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
            <p className="w-setting-description">
              Default difficulty for learning widgets
            </p>
          </div>
        );

      case 'adaptiveDifficulty':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.adaptiveDifficulty}
                onChange={(e) => updateSetting('adaptiveDifficulty', e.target.checked)}
              />
              Adaptive Difficulty
            </label>
            <p className="w-setting-description">
              Automatically adjust difficulty based on your performance
            </p>
          </div>
        );

      case 'hintsEnabled':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.hintsEnabled}
                onChange={(e) => updateSetting('hintsEnabled', e.target.checked)}
              />
              Enable Hints
            </label>
            <p className="w-setting-description">
              Show helpful hints when available
            </p>
          </div>
        );

      case 'preferredLanguage':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-label">Preferred Language</label>
            <select
              value={settings.preferredLanguage}
              onChange={(e) => updateSetting('preferredLanguage', e.target.value)}
              className="w-setting-select"
            >
              <option value="en">English</option>
              <option value="es">Español</option>
              <option value="fr">Français</option>
              <option value="de">Deutsch</option>
              <option value="zh">中文</option>
              <option value="ja">日本語</option>
            </select>
            <p className="w-setting-description">
              Language for multi-language widgets
            </p>
          </div>
        );

      case 'audioEnabled':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.audioEnabled}
                onChange={(e) => updateSetting('audioEnabled', e.target.checked)}
              />
              Enable Audio
            </label>
            <p className="w-setting-description">
              Play sounds and audio feedback in widgets
            </p>
          </div>
        );

      case 'soundVolume':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-label">Sound Volume</label>
            <div 
              className="w-range-input-wrapper" 
              style={{ 
                '--range-progress': `${settings.soundVolume * 100}%` 
              }}
            >
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings.soundVolume}
                onInput={(e) => {
                  const newValue = parseFloat(e.target.value);
                  // Update visual feedback immediately without triggering re-render
                  e.target.parentNode.style.setProperty(
                    '--range-progress', 
                    `${newValue * 100}%`
                  );
                  // Update the displayed value
                  const valueDisplay = e.target.parentNode.parentNode.querySelector('.w-range-value-current');
                  if (valueDisplay) {
                    valueDisplay.textContent = `${Math.round(newValue * 100)}%`;
                  }
                }}
                onChange={(e) => {
                  const newValue = parseFloat(e.target.value);
                  updateSetting('soundVolume', newValue);
                }}
                className="w-setting-input"
                disabled={!settings.audioEnabled}
              />
            </div>
            <div className="w-range-value-display">
              <span className="w-range-value-min">🔇</span>
              <span className="w-range-value-current">{Math.round(settings.soundVolume * 100)}%</span>
              <span className="w-range-value-max">🔊</span>
            </div>
          </div>
        );

      case 'hapticFeedback':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.hapticFeedback}
                onChange={(e) => updateSetting('hapticFeedback', e.target.checked)}
              />
              Haptic Feedback
            </label>
            <p className="w-setting-description">
              Vibration feedback on mobile devices
            </p>
          </div>
        );

      case 'defaultDelay':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-label">Default Timing</label>
            <div 
              className="w-range-input-wrapper" 
              style={{ 
                '--range-progress': `${((settings.defaultDelay - 1.0) / (7.5 - 1.0)) * 100}%` 
              }}
            >
              <input
                type="range"
                min="1.0"
                max="7.5"
                step="0.25"
                value={settings.defaultDelay}
                onInput={(e) => {
                  const newValue = parseFloat(e.target.value);
                  // Update visual feedback immediately without triggering re-render
                  e.target.parentNode.style.setProperty(
                    '--range-progress', 
                    `${((newValue - 1.0) / (7.5 - 1.0)) * 100}%`
                  );
                  // Update the displayed value
                  const valueDisplay = e.target.parentNode.parentNode.querySelector('.w-range-value-current');
                  if (valueDisplay) {
                    valueDisplay.textContent = `${newValue}s`;
                  }
                }}
                onChange={(e) => {
                  const newValue = parseFloat(e.target.value);
                  updateSetting('defaultDelay', newValue);
                }}
                className="w-setting-input"
              />
            </div>
            <div className="w-range-value-display">
              <span className="w-range-value-min">1.0s</span>
              <span className="w-range-value-current">{settings.defaultDelay}s</span>
              <span className="w-range-value-max">7.5s</span>
            </div>
            <p className="w-setting-description">
              Default timing for transitions and auto-advance delays
            </p>
          </div>
        );

      case 'autoAdvance':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.autoAdvance}
                onChange={(e) => updateSetting('autoAdvance', e.target.checked)}
              />
              Auto-Advance
            </label>
            <p className="w-setting-description">
              Automatically advance to next question after correct answers
            </p>
          </div>
        );

      case 'theme':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-label">Theme</label>
            <select
              value={settings.theme}
              onChange={(e) => updateSetting('theme', e.target.value)}
              className="w-setting-select"
            >
              <option value="auto">Auto (System)</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="high-contrast">High Contrast</option>
            </select>
            <p className="w-setting-description">
              Choose your preferred color theme
            </p>
          </div>
        );

      case 'fontSize':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-label">Font Size</label>
            <select
              value={settings.fontSize}
              onChange={(e) => updateSetting('fontSize', e.target.value)}
              className="w-setting-select"
            >
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
            </select>
            <p className="w-setting-description">
              Adjust text size for better readability
            </p>
          </div>
        );

      case 'animations':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.animations}
                onChange={(e) => updateSetting('animations', e.target.checked)}
              />
              Enable Animations
            </label>
            <p className="w-setting-description">
              Show smooth transitions and animations
            </p>
          </div>
        );

      case 'reducedMotion':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.reducedMotion}
                onChange={(e) => updateSetting('reducedMotion', e.target.checked)}
              />
              Reduce Motion
            </label>
            <p className="w-setting-description">
              Minimize animations for motion sensitivity
            </p>
          </div>
        );

      case 'screenReaderMode':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.screenReaderMode}
                onChange={(e) => updateSetting('screenReaderMode', e.target.checked)}
              />
              Screen Reader Mode
            </label>
            <p className="w-setting-description">
              Optimize for screen reader compatibility
            </p>
          </div>
        );

      case 'highContrastMode':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.highContrastMode}
                onChange={(e) => updateSetting('highContrastMode', e.target.checked)}
              />
              High Contrast Mode
            </label>
            <p className="w-setting-description">
              Increase visual contrast for better visibility
            </p>
          </div>
        );

      case 'keyboardShortcuts':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.keyboardShortcuts}
                onChange={(e) => updateSetting('keyboardShortcuts', e.target.checked)}
              />
              Enable Keyboard Shortcuts
            </label>
            <p className="w-setting-description">
              Use keyboard shortcuts for navigation
            </p>
          </div>
        );

      case 'anonymousMode':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.anonymousMode}
                onChange={(e) => updateSetting('anonymousMode', e.target.checked)}
              />
              Anonymous Mode
            </label>
            <p className="w-setting-description">
              Don't track progress or statistics
            </p>
          </div>
        );

      case 'shareProgress':
        return (
          <div key={settingKey} className="w-setting-group">
            <label className="w-setting-checkbox">
              <input
                type="checkbox"
                checked={settings.shareProgress}
                onChange={(e) => updateSetting('shareProgress', e.target.checked)}
                disabled={settings.anonymousMode}
              />
              Allow Progress Sharing
            </label>
            <p className="w-setting-description">
              Share achievements and progress with others
            </p>
          </div>
        );

      default:
        return null;
    }
  };

  /**
   * Settings Modal Component
   */
  const SettingsModal = () => {
    if (!showGlobalSettings) return null;

    // Create tabs array, adding "Used Settings" tab if usedSettings is provided
    const tabs = [];
    if (usedSettings.length > 0) {
      tabs.push({ id: 'used', label: 'Used Settings', icon: '⭐' });
    }
    tabs.push(
      { id: 'general', label: 'General', icon: '⚙️' },
      { id: 'audio', label: 'Audio & Feedback', icon: '🔊' },
      { id: 'visual', label: 'Visual', icon: '🎨' },
      { id: 'accessibility', label: 'Accessibility', icon: '♿' },
      { id: 'privacy', label: 'Privacy', icon: '🔒' }
    );

    return (
      <div className="w-settings-overlay">
        <div ref={modalRef} className="w-settings-modal">
          <div className="w-settings-header">
            <h2 className="w-settings-title">Global Settings</h2>
            <button
              onClick={toggleGlobalSettings}
              className="w-settings-close"
              aria-label="Close settings"
            >
              ×
            </button>
          </div>

          <div className="w-settings-tabs">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-settings-tab ${activeTab === tab.id ? 'active' : ''}`}
              >
                <span className="w-settings-tab-icon">{tab.icon}</span>
                <span className="w-settings-tab-label">{tab.label}</span>
              </button>
            ))}
          </div>

          <div className="w-settings-form">
            {/* Used Settings Tab */}
            {activeTab === 'used' && (
              <>
                {usedSettings.length > 0 ? (
                  usedSettings.map(settingKey => renderSetting(settingKey))
                ) : (
                  <div className="w-setting-group">
                    <p className="w-setting-description">
                      No specific settings have been configured for this widget.
                    </p>
                  </div>
                )}
              </>
            )}

            {/* General Tab */}
            {activeTab === 'general' && (
              <>
                {renderSetting('userName')}
                {renderSetting('difficulty')}
                {renderSetting('adaptiveDifficulty')}
                {renderSetting('hintsEnabled')}
                {renderSetting('preferredLanguage')}
              </>
            )}

            {/* Audio & Feedback Tab */}
            {activeTab === 'audio' && (
              <>
                {renderSetting('audioEnabled')}
                {renderSetting('soundVolume')}
                {renderSetting('hapticFeedback')}
                {renderSetting('defaultDelay')}
                {renderSetting('autoAdvance')}
              </>
            )}

            {/* Visual Tab */}
            {activeTab === 'visual' && (
              <>
                {renderSetting('theme')}
                {renderSetting('fontSize')}
                {renderSetting('animations')}
                {renderSetting('reducedMotion')}
              </>
            )}

            {/* Accessibility Tab */}
            {activeTab === 'accessibility' && (
              <>
                {renderSetting('screenReaderMode')}
                {renderSetting('highContrastMode')}
                {renderSetting('keyboardShortcuts')}
              </>
            )}

            {/* Privacy Tab */}
            {activeTab === 'privacy' && (
              <>
                {renderSetting('anonymousMode')}
                {renderSetting('shareProgress')}
              </>
            )}
          </div>

          <div className="w-settings-actions">
            <button
              onClick={resetSettings}
              className="w-settings-button w-settings-button-secondary"
            >
              Reset to Defaults
            </button>
            <button
              onClick={toggleGlobalSettings}
              className="w-settings-button w-settings-button-primary"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    );
  };

  return {
    settings,
    updateSetting,
    updateSettings,
    resetSettings,
    showGlobalSettings,
    toggleGlobalSettings,
    readGlobalSettings,
    SettingsModal,
    SettingsToggle
  };
};

export default useGlobalSettings;