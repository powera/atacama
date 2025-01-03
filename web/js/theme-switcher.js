
class ThemeSwitcher {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.initializeTheme();
        this.setupSwitcher();
        this.setupThemeObserver();
    }

    initializeTheme() {
        // Apply theme from localStorage or system preference
        if (!this.theme) {
            this.theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        document.documentElement.setAttribute('data-theme', this.theme);
        
        // Initialize layout based on theme
        if (this.theme === 'high-contrast') {
            this.handleHighContrastLayout();
        } else {
            this.ensureDefaultState();
        }
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
        
        // Handle theme-specific layout changes
        if (newTheme === 'high-contrast') {
            this.handleHighContrastLayout();
        } else {
            this.removeHighContrastLayout();
        }
    }

    setupThemeObserver() {
        // Watch for theme changes that might happen outside this class
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'data-theme') {
                    const newTheme = document.documentElement.getAttribute('data-theme');
                    if (newTheme === 'high-contrast') {
                        this.handleHighContrastLayout();
                    } else {
                        this.removeHighContrastLayout();
                    }
                }
            });
        });

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme']
        });
    }

    handleHighContrastLayout() {
        const messageContainers = document.querySelectorAll('.message');
        messageContainers.forEach(container => {
            if (!container.querySelector('.message-main')) {
                this.setupHighContrastContainer(container);
            }
        });

        // Ensure visibility of .colortext-content and interactivity of .sigil
        document.querySelectorAll('.colortext-content').forEach(content => {
            content.style.display = 'block';
        });
        document.querySelectorAll('.sigil').forEach(sigil => {
            sigil.style.pointerEvents = 'auto';
            sigil.style.cursor = 'pointer';
        });
    }

    setupHighContrastContainer(messageContainer) {
        // Store original content
        const content = messageContainer.innerHTML;
        messageContainer.innerHTML = '';

        // Create main content area
        const mainContent = document.createElement('div');
        mainContent.className = 'message-main';
        mainContent.innerHTML = content;

        // Create sidebar
        const sidebar = document.createElement('div');
        sidebar.className = 'message-sidebar';

        // Add both sections to container
        messageContainer.appendChild(mainContent);
        messageContainer.appendChild(sidebar);

        // Move color blocks to sidebar
        this.moveColorBlocksToSidebar(mainContent, sidebar);
    }

    moveColorBlocksToSidebar(mainContent, sidebar) {
        const colorBlocks = mainContent.querySelectorAll('[class^="color-"]');
        const processedBlocks = new Set();

        colorBlocks.forEach(block => {
            const content = block.querySelector('.colortext-content');
            if (content && !processedBlocks.has(content)) {
                processedBlocks.add(content);

                // Create container for this block in sidebar
                const container = document.createElement('div');
                container.className = 'color-block-container';

                // Clone sigil and content
                const sigilClone = block.querySelector('.sigil').cloneNode(true);
                const contentClone = content.cloneNode(true);

                // Add to sidebar
                container.appendChild(sigilClone);
                container.appendChild(contentClone);
                sidebar.appendChild(container);

                // Ensure content is visible in sidebar
                contentClone.style.display = 'inline';
            }
        });
    }

    removeHighContrastLayout() {
        const messageContainers = document.querySelectorAll('.message');
        messageContainers.forEach(container => {
            const mainContent = container.querySelector('.message-main');
            if (mainContent) {
                container.innerHTML = mainContent.innerHTML;
            }
        });

        // Reset .colortext-content and .sigil interactivity
        document.querySelectorAll('.colortext-content').forEach(content => {
            content.style.display = '';
        });
        document.querySelectorAll('.sigil').forEach(sigil => {
            sigil.style.pointerEvents = '';
            sigil.style.cursor = '';
        });
    }

    ensureDefaultState() {
        // Reset any custom styles for other themes
        document.querySelectorAll('.colortext-content').forEach(content => {
            content.style.display = '';
        });
        document.querySelectorAll('.sigil').forEach(sigil => {
            sigil.style.pointerEvents = '';
            sigil.style.cursor = '';
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new ThemeSwitcher());
} else {
    new ThemeSwitcher();
}
