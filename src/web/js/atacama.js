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
    }

    setupThemeSwitcher() {
        const switcher = document.createElement('div');
        switcher.className = 'theme-switcher';
        switcher.innerHTML = `
            <button class="theme-button" aria-label="Switch theme">
                <span class="theme-icon">🌗</span>
            </button>
            <div class="theme-menu">
                <button data-theme-option="light">Light</button>
                <button data-theme-option="dark">Dark</button>
                <button data-theme-option="grayscale">Grayscale</button>
                <hr>
                <button data-expand-action="expand-all">Expand All</button>
                <button data-expand-action="collapse-all">Collapse All</button>
                <button data-expand-action="restore-default">Restore Default</button>
            </div>
        `;

        switcher.querySelectorAll('[data-theme-option]').forEach(button => {
            button.addEventListener('click', () => this.setTheme(button.dataset.themeOption));
        });

        switcher.querySelectorAll('[data-expand-action]').forEach(button => {
            button.addEventListener('click', () => this.handleExpandAction(button.dataset.expandAction));
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
        // Clean up any active Youtube players before theme switch
        document.querySelectorAll('.youtube-player iframe').forEach(iframe => {
            iframe.remove();
        });

        // Re-collapse any expanded players in main content
        document.querySelectorAll('.youtube-embed-container .colortext-content.expanded')
            .forEach(container => {
                container.classList.remove('expanded');
            });
        this.theme = newTheme;
        localStorage.setItem('theme', newTheme);
        
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

            if (e.target.closest('.mlq-collapse')) {
                this.handleMlqCollapse(e);
            }
            if (e.target.closest('.fen-toggle')) {
                const button = e.target.closest('.fen-toggle');
                const fenText = button.nextElementSibling;
                if (fenText && fenText.classList.contains('fen-text')) {
                    const isHidden = fenText.style.display === 'none';
                    fenText.style.display = isHidden ? 'block' : 'none';
                    button.textContent = isHidden ? 'Hide position (FEN)' : 'Show position (FEN)';
                }
            }
        });

        document.addEventListener('keydown', this.handleKeyDown);
    }

    /**
     * Initializes or unloads Youtube player in a container
     */
    handleYoutubePlayer(container, isExpanded) {
        const player = container.querySelector('.youtube-player');
        if (!player) return;
        
        const videoId = player.dataset.videoId;
        if (!videoId) return;
        
        if (isExpanded && !player.querySelector('iframe')) {
            // Create iframe when expanding
            const iframe = document.createElement('iframe');
            iframe.setAttribute('frameborder', '0');
            iframe.setAttribute('allowfullscreen', '1');
            iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
            iframe.style.width = '100%';
            iframe.style.height = '100%';
            iframe.src = `https://www.youtube.com/embed/${videoId}?enablejsapi=1`;
            player.appendChild(iframe);
        } else if (!isExpanded && player.querySelector('iframe')) {
            // Remove iframe when collapsing
            player.innerHTML = '';
        }
    }


    /**
     * Handles clicks on sigil elements, toggling content visibility
     */
    handleSigilClick(e) {
        
        const colorBlock = e.target.closest('.colorblock, [class^="color-"]');
        if (!colorBlock) return;
        
        const content = colorBlock.querySelector('.colortext-content');
        const sigil = colorBlock.querySelector('.sigil');
        if (!content || !sigil || e.target.tagName === 'A') return;
        const isExpanding = !content.classList.contains('expanded');
        content.classList.toggle('expanded');

        // Handle Youtube player if this is a video container
        if (colorBlock.classList.contains('youtube-embed-container')) {
            this.handleYoutubePlayer(content, isExpanding);
        }

        /* Disable rotation
        * sigil.style.transform = content.classList.contains('expanded') ? 'rotate(30deg)' : '';
        * sigil.style.transition = 'transform 0.3s ease';
        * */
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
     * Handles clicks on mlq collapse buttons
     */
    handleMlqCollapse(e) {
        const button = e.target.closest('.mlq-collapse');
        const block = button.closest('.mlq');
        const icon = button.querySelector('.mlq-collapse-icon');
        
        block.classList.toggle('collapsed');
        if (!/\p{Emoji}/u.test(icon.textContent)) {
            icon.textContent = block.classList.contains('collapsed') ? '+' : '−';
        }
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
     * Handles expand/collapse actions from the theme menu
     */
    handleExpandAction(action) {
        switch (action) {
            case 'expand-all':
                this.expandAll();
                break;
            case 'collapse-all':
                this.collapseAll();
                break;
            case 'restore-default':
                this.restoreDefault();
                break;
        }
    }

    /**
     * Expands all colortext boxes and mlq boxes
     */
    expandAll() {
        // Expand all colortext content (except YouTube players)
        document.querySelectorAll('.colortext-content').forEach(content => {
            if (!content.classList.contains('expanded')) {
                const colorBlock = content.closest('.colorblock, [class^="color-"]');
                // Skip YouTube embed containers
                if (colorBlock && colorBlock.classList.contains('youtube-embed-container')) {
                    return;
                }
                content.classList.add('expanded');
            }
        });

        // Expand all mlq boxes (remove collapsed class)
        document.querySelectorAll('.mlq.collapsed').forEach(mlq => {
            mlq.classList.remove('collapsed');
            const icon = mlq.querySelector('.mlq-collapse-icon');
            if (icon && !/\p{Emoji}/u.test(icon.textContent)) {
                icon.textContent = '−';
            }
        });
    }

    /**
     * Collapses all colortext boxes and mlq boxes
     */
    collapseAll() {
        // Collapse all colortext content (including YouTube players)
        document.querySelectorAll('.colortext-content.expanded').forEach(content => {
            content.classList.remove('expanded');
            
            // Handle Youtube players if this is a video container
            const colorBlock = content.closest('.colorblock, [class^="color-"]');
            if (colorBlock && colorBlock.classList.contains('youtube-embed-container')) {
                this.handleYoutubePlayer(content, false);
            }
        });

        // Collapse all mlq boxes (add collapsed class)
        document.querySelectorAll('.mlq').forEach(mlq => {
            if (!mlq.classList.contains('collapsed')) {
                mlq.classList.add('collapsed');
                const icon = mlq.querySelector('.mlq-collapse-icon');
                if (icon && !/\p{Emoji}/u.test(icon.textContent)) {
                    icon.textContent = '+';
                }
            }
        });
    }

    /**
     * Restores default state: mlq boxes expanded, colortext boxes collapsed
     */
    restoreDefault() {
        // Collapse all colortext content (default state, except YouTube players)
        document.querySelectorAll('.colortext-content.expanded').forEach(content => {
            const colorBlock = content.closest('.colorblock, [class^="color-"]');
            // Skip YouTube embed containers
            if (colorBlock && colorBlock.classList.contains('youtube-embed-container')) {
                return;
            }
            content.classList.remove('expanded');
        });

        // Expand all mlq boxes (default state - remove collapsed class)
        document.querySelectorAll('.mlq.collapsed').forEach(mlq => {
            mlq.classList.remove('collapsed');
            const icon = mlq.querySelector('.mlq-collapse-icon');
            if (icon && !/\p{Emoji}/u.test(icon.textContent)) {
                icon.textContent = '−';
            }
        });
    }


}

// Create a single instance when the DOM is ready
const viewer = new AtacamaViewer();
