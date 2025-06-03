// Access React hooks from the global React object
const { useState, useEffect, useRef, useCallback } = React;

/**
 * Default settings configuration
 */
const DEFAULT_SETTINGS = {
  audioEnabled: true,
  difficulty: 'medium', // 'easy', 'medium', 'hard'
  userName: '',
  animations: true,
  autoAdvance: false,
  defaultDelay: 2.5 // seconds, range 1.0 to 7.5
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
 *   - resetSettings: function to reset all settings to defaults
 *   - showGlobalSettings: boolean indicating if settings modal is open
 *   - toggleGlobalSettings: function to toggle settings modal
 *   - readGlobalSettings: function to get current settings (for compatibility)
 * 
 * @example
 * const MyWidget = () => {
 *   const { 
 *     settings, 
 *     updateSetting, 
 *     showGlobalSettings, 
 *     toggleGlobalSettings,
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

          <div className="w-settings-form">
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

            {/* Difficulty Setting */}
            <div className="w-setting-group">
              <label className="w-setting-label">Difficulty Level</label>
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

            {/* Default Delay Setting */}
            <div className="w-setting-group">
              <label className="w-setting-label">Default Delay</label>
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
                  step="0.125"
                  value={settings.defaultDelay}
                  onChange={(e) => {
                    const newValue = parseFloat(e.target.value);
                    updateSetting('defaultDelay', newValue);
                    // Update the progress variable directly for immediate visual feedback
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
    resetSettings,
    showGlobalSettings,
    toggleGlobalSettings,
    readGlobalSettings,
    SettingsModal,
    SettingsToggle
  };
};

export default useGlobalSettings;