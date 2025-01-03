class AtacamaViewer {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.currentAnnotation = null;
        this.touchStartY = 0;
        this.currentTranslateY = 0;
        
        this.initializeTheme();
        this.setupThemeSwitcher();
        this.setupThemeObserver();
        this.bindContentEvents();
    }

    initializeTheme() {
        if (!this.theme) {
            this.theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
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

    bindContentEvents() {
        // Handle color block expansions
        document.querySelectorAll('[class^="color-"]').forEach(block => {
            const content = block.querySelector('.colortext-content');
            const sigil = block.querySelector('.sigil');
            if (!content || !sigil) return;

            sigil.addEventListener('click', (e) => {
                // Don't expand if in high contrast mode or clicking a link
                if (this.theme === 'high-contrast' || e.target.tagName === 'A') return;
                content.classList.toggle('expanded');
            });
        });

        // Handle Chinese annotations
        document.querySelectorAll('.annotated-chinese').forEach(annotation => {
            const pinyin = annotation.getAttribute('data-pinyin');
            const definition = annotation.getAttribute('data-definition');
            
            const inlineAnnotation = document.createElement('div');
            inlineAnnotation.className = 'annotation-inline';
            inlineAnnotation.innerHTML = `
                <span class="pinyin">${pinyin}</span>
                <span class="definition">${definition}</span>
            `;
            
            annotation.parentNode.insertBefore(inlineAnnotation, annotation.nextSibling);
            
            annotation.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                document.querySelectorAll('.annotation-inline.expanded').forEach(other => {
                    if (other !== inlineAnnotation) {
                        other.classList.remove('expanded');
                    }
                });
                
                inlineAnnotation.classList.toggle('expanded');
            });
        });

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.colortext-content.expanded, .annotation-inline.expanded')
                    .forEach(el => el.classList.remove('expanded'));
            }
        });
    }

    handleHighContrastLayout() {
        const messageContainers = document.querySelectorAll('.message');
        messageContainers.forEach(container => {
            if (!container.querySelector('.message-main')) {
                this.setupHighContrastContainer(container);
            }
        });

        document.querySelectorAll('.colortext-content').forEach(content => {
            content.style.display = 'block';
        });
    }

    setupHighContrastContainer(messageContainer) {
        const content = messageContainer.innerHTML;
        messageContainer.innerHTML = '';

        const mainContent = document.createElement('div');
        mainContent.className = 'message-main';
        mainContent.innerHTML = content;

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

        document.querySelectorAll('.colortext-content').forEach(content => {
            content.style.display = '';
        });
        
        // Rebind events after layout changes
        this.bindContentEvents();
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new AtacamaViewer());
} else {
    new AtacamaViewer();
}
