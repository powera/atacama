class AtacamaViewer {
    constructor() {
        // Initialize state
        this.theme = localStorage.getItem('theme') || 'light';
        
        // Bind methods to maintain correct 'this' context
        this.handleSigilClick = this.handleSigilClick.bind(this);
        this.handleAnnotationClick = this.handleAnnotationClick.bind(this);
        this.handleKeyDown = this.handleKeyDown.bind(this);
        
        // Set up the viewer
        this.initializeTheme();
        this.setupThemeSwitcher();
        this.setupThemeObserver();
        this.setupEventDelegation();
    }

    initializeTheme() {
        // Set initial theme based on system preference if not stored
        if (!this.theme) {
            this.theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        document.documentElement.setAttribute('data-theme', this.theme);
        
        // Apply high contrast layout if needed
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

        // Add theme switching event listeners
        switcher.querySelectorAll('[data-theme]').forEach(button => {
            button.addEventListener('click', () => this.setTheme(button.dataset.theme));
        });

        document.body.appendChild(switcher);
    }

    setupEventDelegation() {
        // Use event delegation for content interactions
        document.addEventListener('click', (e) => {
            // Handle sigil clicks
            if (e.target.closest('.sigil')) {
                this.handleSigilClick(e);
            }
            
            // Handle Chinese annotation clicks
            if (e.target.closest('.annotated-chinese')) {
                this.handleAnnotationClick(e);
            }
        });

        // Global keyboard handling
        document.addEventListener('keydown', this.handleKeyDown);
    }

    handleSigilClick(e) {
        if (this.theme === 'high-contrast') return;
        
        const colorBlock = e.target.closest('[class^="color-"]');
        if (!colorBlock) return;
        
        const content = colorBlock.querySelector('.colortext-content');
        if (!content) return;
        
        if (e.target.tagName === 'A') return;
        
        content.classList.toggle('expanded');
    }

    handleAnnotationClick(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const annotation = e.target.closest('.annotated-chinese');
        const inlineAnnotation = annotation.nextElementSibling;
        
        if (!inlineAnnotation?.classList.contains('annotation-inline')) {
            this.createAnnotationElement(annotation);
            return;
        }
        
        // Close other annotations
        document.querySelectorAll('.annotation-inline.expanded').forEach(other => {
            if (other !== inlineAnnotation) {
                other.classList.remove('expanded');
            }
        });
        
        inlineAnnotation.classList.toggle('expanded');
    }

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

    handleKeyDown(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.colortext-content.expanded, .annotation-inline.expanded')
                .forEach(el => el.classList.remove('expanded'));
        }
    }

    setTheme(newTheme) {
        this.theme = newTheme;
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        if (newTheme === 'high-contrast') {
            this.handleHighContrastLayout();
        } else {
            this.removeHighContrastLayout();
        }
    }

    setupThemeObserver() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'data-theme') {
                    const newTheme = document.documentElement.getAttribute('data-theme');
                    this.theme = newTheme;
                    
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
    }

    setupHighContrastContainer(messageContainer) {
        // Store original content
        const originalContent = messageContainer.innerHTML;
        messageContainer.innerHTML = '';

        // Create main content area
        const mainContent = document.createElement('div');
        mainContent.className = 'message-main';
        mainContent.innerHTML = originalContent;

        // Ensure colortext is hidden in main content
        mainContent.querySelectorAll('.colortext-content').forEach(content => {
            content.style.display = 'none';
        });

        // Create sidebar
        const sidebar = document.createElement('div');
        sidebar.className = 'message-sidebar';

        messageContainer.appendChild(mainContent);
        messageContainer.appendChild(sidebar);

        this.moveColorBlocksToSidebar(mainContent, sidebar);
    }

    moveColorBlocksToSidebar(mainContent, sidebar) {
        const colorBlocks = mainContent.querySelectorAll('[class^="color-"]');
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

                // Ensure content is visible in sidebar only
                contentClone.style.display = 'inline';
            }
        });
    }

    removeHighContrastLayout() {
        const messageContainers = document.querySelectorAll('.message');
        messageContainers.forEach(container => {
            const mainContent = container.querySelector('.message-main');
            if (mainContent) {
                // Preserve the original structure
                container.innerHTML = mainContent.innerHTML;
                
                // Reset colortext display
                container.querySelectorAll('.colortext-content').forEach(content => {
                    content.style.display = '';
                });
            }
        });
    }
}

// Initialize viewer when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new AtacamaViewer());
} else {
    new AtacamaViewer();
}
