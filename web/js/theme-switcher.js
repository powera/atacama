class ThemeSwitcher {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.initializeTheme();
        this.setupSwitcher();
    }

    initializeTheme() {
        // Apply theme from localStorage or system preference
        if (!this.theme) {
            this.theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        document.documentElement.setAttribute('data-theme', this.theme);
    }

    setupSwitcher() {
        // Create theme switcher button
        const switcher = document.createElement('div');
        switcher.className = 'theme-switcher';
        switcher.innerHTML = `
            <button class="theme-button" aria-label="Switch theme">
                <span class="theme-icon">🌗</span>
            </button>
            <div class="theme-menu">
                <button data-theme="light">Light</button>
                <button data-theme="dark">Dark</button>
                <button data-theme="high-contrast">High Contrast</button>
            </div>
        `;

        // Add event listeners
        switcher.querySelectorAll('[data-theme]').forEach(button => {
            button.addEventListener('click', () => this.setTheme(button.dataset.theme));
        });

        // Insert switcher into page
        document.body.appendChild(switcher);
    }

    setTheme(newTheme) {
        this.theme = newTheme;
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new ThemeSwitcher());
} else {
    new ThemeSwitcher();
}
