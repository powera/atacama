class AtacamaViewer {
    /**
     * Initializes the viewer and sets up event handling, but defers DOM operations
     * until the DOMContentLoaded event.
     */
    constructor() {
        // Initialize state
        this.theme = localStorage.getItem('theme') || 'light';
        
        // Store observer as instance variable so we can disconnect/reconnect it
        this.themeObserver = null;
        
        // Bind methods to maintain correct 'this' context
        this.handleSigilClick = this.handleSigilClick.bind(this);
        this.handleAnnotationClick = this.handleAnnotationClick.bind(this);
        this.handleKeyDown = this.handleKeyDown.bind(this);
        
        // Defer initialization until DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initialize());
        } else {
            this.initialize();
        }
    }

    /**
     * Performs all DOM-dependent initialization steps after the
     * document is ready
     */
    initialize() {
        this.initializeTheme();
        this.setupThemeSwitcher();
        this.setupThemeObserver();
        this.setupEventDelegation();
    }

    initializeTheme() {
        if (!this.theme) {
            this.theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        // Apply theme without triggering observer (since it isn't set up yet)
        document.documentElement.setAttribute('data-theme', this.theme);
        
        if (this.theme === 'high-contrast') {
            this.handleHighContrastLayout();
        }
    }

    setupThemeSwitcher() {
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

        switcher.querySelectorAll('[data-theme]').forEach(button => {
            button.addEventListener('click', () => this.setTheme(button.dataset.theme));
        });

        document.body.appendChild(switcher);
    }

    /**
     * Sets up an observer to handle theme changes from external sources
     */
    setupThemeObserver() {
        // Create observer to handle external theme changes
        this.themeObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'data-theme') {
                    // Only handle changes that come from outside our code
                    const newTheme = document.documentElement.getAttribute('data-theme');
                    this.handleThemeChange(newTheme);
                }
            });
        });

        // Start observing
        this.themeObserver.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme']
        });
    }

    setTheme(newTheme) {
        // Temporarily stop observing to prevent handling our own change
        this.themeObserver.disconnect();
        
        // Update theme
        document.documentElement.setAttribute('data-theme', newTheme);
        
        // Handle the theme change
        this.handleThemeChange(newTheme);
        
        // Resume observing for external changes
        this.themeObserver.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme']
        });
    }

    handleThemeChange(newTheme) {
        this.theme = newTheme;
        localStorage.setItem('theme', newTheme);
        
        if (newTheme === 'high-contrast') {
            this.handleHighContrastLayout();
        } else {
            this.removeHighContrastLayout();
        }
    }

    populateSidebar(mainContent, sidebar) {
        // Clear any existing content in the sidebar
        sidebar.innerHTML = '';

        // Find all color blocks in the main content
        const colorBlocks = mainContent.querySelectorAll('.colorblock, [class^="color-"]');
        const processedBlocks = new Set();

        colorBlocks.forEach(block => {
            const content = block.querySelector('.colortext-content');
            if (content && !processedBlocks.has(content)) {
                processedBlocks.add(content);

                // Create container for this block
                const container = document.createElement('div');
                container.className = 'color-block-container';

                // Clone sigil and content
                const sigilClone = block.querySelector('.sigil').cloneNode(true);
                const contentClone = content.cloneNode(true);

                container.appendChild(sigilClone);
                container.appendChild(contentClone);
                sidebar.appendChild(container);

                // Make sidebar content visible
                contentClone.style.display = 'inline';

                // Hide original content
                content.style.display = 'none';
            }
        });
    }

    /**
     * Sets up event delegation for content interactions to handle dynamically added elements
     */
    setupEventDelegation() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('.sigil')) {
                this.handleSigilClick(e);
            }
            
            if (e.target.closest('.annotated-chinese')) {
                this.handleAnnotationClick(e);
            }
        });

        document.addEventListener('keydown', this.handleKeyDown);
    }

    /**
     * Handles clicks on sigil elements, toggling content visibility in non-high-contrast mode
     */
    handleSigilClick(e) {
        if (this.theme === 'high-contrast') return;
        
        const colorBlock = e.target.closest('.colorblock, [class^="color-"]');
        if (!colorBlock) return;
        
        const content = colorBlock.querySelector('.colortext-content');
        if (!content || e.target.tagName === 'A') return;
        
        content.classList.toggle('expanded');
    }

    /**
     * Handles clicks on Chinese annotations, creating or toggling the annotation display
     */
    handleAnnotationClick(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const annotation = e.target.closest('.annotated-chinese');
        const inlineAnnotation = annotation.nextElementSibling;
        
        if (!inlineAnnotation?.classList.contains('annotation-inline')) {
            this.createAnnotationElement(annotation);
            return;
        }
        
        document.querySelectorAll('.annotation-inline.expanded').forEach(other => {
            if (other !== inlineAnnotation) {
                other.classList.remove('expanded');
            }
        });
        
        inlineAnnotation.classList.toggle('expanded');
    }

    /**
     * Creates an inline annotation element for Chinese text
     */
    createAnnotationElement(annotation) {
        const pinyin = annotation.getAttribute('data-pinyin');
        const definition = annotation.getAttribute('data-definition');
        
        const inlineAnnotation = document.createElement('div');
        inlineAnnotation.className = 'annotation-inline';
        inlineAnnotation.innerHTML = `
            <span class="pinyin">${pinyin}</span>
            <span class="definition">${definition}</span>
        `;
        
        annotation.parentNode.insertBefore(inlineAnnotation, annotation.nextSibling);
        inlineAnnotation.classList.add('expanded');
    }

    /**
     * Handles global keyboard events, particularly for closing expanded elements
     */
    handleKeyDown(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.colortext-content.expanded, .annotation-inline.expanded')
                .forEach(el => el.classList.remove('expanded'));
        }
    }


    /**
     * Applies the high-contrast layout to all message containers
     */
    handleHighContrastLayout() {
        document.querySelectorAll('.message-body').forEach(container => {
            const mainContent = container.querySelector('.message-main');
            const sidebar = container.querySelector('.message-sidebar');
            
            if (!sidebar.hasAttribute('data-processed')) {
                this.populateSidebar(mainContent, sidebar);
                sidebar.setAttribute('data-processed', 'true');
            }
        });
    }

    /**
     * Creates sidebar content blocks from main content colored sections
     */
    moveColorBlocksToSidebar(mainContent, sidebar) {
        const colorBlocks = mainContent.querySelectorAll('.colorblock, [class^="color-"]');
        const processedBlocks = new Set();

        colorBlocks.forEach(block => {
            const content = block.querySelector('.colortext-content');
            if (content && !processedBlocks.has(content)) {
                processedBlocks.add(content);

                const container = document.createElement('div');
                container.className = 'color-block-container';

                const sigilClone = block.querySelector('.sigil').cloneNode(true);
                const contentClone = content.cloneNode(true);

                container.appendChild(sigilClone);
                container.appendChild(contentClone);
                sidebar.appendChild(container);

                contentClone.style.display = 'inline';
            }
        });
    }

    /**
     * Removes the high-contrast layout and restores the default view
     */
    removeHighContrastLayout() {
        document.querySelectorAll('.message-body').forEach(container => {
            container.querySelectorAll('.colortext-content').forEach(content => {
                content.style.display = '';
            });

            const sidebar = container.querySelector('.message-sidebar');
            sidebar.innerHTML = '';
            sidebar.removeAttribute('data-processed');
        });
    }
}

// Create a single instance when the DOM is ready
const viewer = new AtacamaViewer();
