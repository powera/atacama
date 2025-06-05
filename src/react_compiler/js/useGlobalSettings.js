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
 *   } = useGlobalSettings();
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
export const useGlobalSettings = () => {
  const [settings, setSettings] = useState(loadSettings);
  const [showGlobalSettings, setShowGlobalSettings] = useState(false);
  const [activeTab, setActiveTab] = useState('general');
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
   * Settings Modal Component
   */
  const SettingsModal = () => {
    if (!showGlobalSettings) return null;

    const tabs = [
      { id: 'general', label: 'General', icon: '⚙️' },
      { id: 'audio', label: 'Audio & Feedback', icon: '🔊' },
      { id: 'visual', label: 'Visual', icon: '🎨' },
      { id: 'accessibility', label: 'Accessibility', icon: '♿' },
      { id: 'privacy', label: 'Privacy', icon: '🔒' }
    ];

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
            {/* General Tab */}
            {activeTab === 'general' && (
              <>
                {/* User Name Setting */}
                <div className="w-setting-group">
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

                {/* Difficulty Setting */}
                <div className="w-setting-group">
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

                {/* Adaptive Difficulty */}
                <div className="w-setting-group">
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

                {/* Hints Setting */}
                <div className="w-setting-group">
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

                {/* Language Setting */}
                <div className="w-setting-group">
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
              </>
            )}

            {/* Audio & Feedback Tab */}
            {activeTab === 'audio' && (
              <>
                {/* Audio Setting */}
                <div className="w-setting-group">
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

                {/* Volume Setting */}
                <div className="w-setting-group">
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
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        updateSetting('soundVolume', newValue);
                        e.target.parentNode.style.setProperty(
                          '--range-progress', 
                          `${newValue * 100}%`
                        );
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

                {/* Haptic Feedback */}
                <div className="w-setting-group">
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

                {/* Default Delay Setting */}
                <div className="w-setting-group">
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
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        updateSetting('defaultDelay', newValue);
                        e.target.parentNode.style.setProperty(
                          '--range-progress', 
                          `${((newValue - 1.0) / (7.5 - 1.0)) * 100}%`
                        );
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

                {/* Auto Advance Setting */}
                <div className="w-setting-group">
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
              </>
            )}

            {/* Visual Tab */}
            {activeTab === 'visual' && (
              <>
                {/* Theme Setting */}
                <div className="w-setting-group">
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

                {/* Font Size Setting */}
                <div className="w-setting-group">
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

                {/* Animations Setting */}
                <div className="w-setting-group">
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

                {/* Reduced Motion */}
                <div className="w-setting-group">
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
              </>
            )}

            {/* Accessibility Tab */}
            {activeTab === 'accessibility' && (
              <>
                {/* Screen Reader Mode */}
                <div className="w-setting-group">
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

                {/* High Contrast Mode */}
                <div className="w-setting-group">
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

                {/* Keyboard Shortcuts */}
                <div className="w-setting-group">
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
              </>
            )}

            {/* Privacy Tab */}
            {activeTab === 'privacy' && (
              <>
                {/* Anonymous Mode */}
                <div className="w-setting-group">
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

                {/* Share Progress */}
                <div className="w-setting-group">
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