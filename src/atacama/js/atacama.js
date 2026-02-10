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

        // Tooltip state
        this.englishTooltip = null;
        this.tooltipHideTimeout = null;
        
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
        this.createEnglishTooltip();
        this.setupEventDelegation();
        this.initializeEnglishAnnotations();
    }

    /**
     * Creates the singleton tooltip element for English annotations
     */
    createEnglishTooltip() {
        this.englishTooltip = document.createElement('div');
        this.englishTooltip.className = 'annotation-english-tooltip';
        document.body.appendChild(this.englishTooltip);

        // Keep tooltip visible when hovering over it
        this.englishTooltip.addEventListener('mouseenter', () => {
            clearTimeout(this.tooltipHideTimeout);
        });
        this.englishTooltip.addEventListener('mouseleave', () => {
            this.hideEnglishTooltip();
        });
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

        // English annotation hover events
        document.addEventListener('mouseover', (e) => {
            const span = e.target.closest('.annotated-english, .annotated-stopword');
            if (span) {
                clearTimeout(this.tooltipHideTimeout);
                this.showEnglishTooltip(span);
            }
        });

        document.addEventListener('mouseout', (e) => {
            const span = e.target.closest('.annotated-english, .annotated-stopword');
            if (span) {
                this.hideEnglishTooltip();
            }
        });

        // Touch support: tap to show, tap elsewhere to dismiss
        document.addEventListener('touchstart', (e) => {
            const span = e.target.closest('.annotated-english, .annotated-stopword');
            if (span) {
                e.preventDefault();
                clearTimeout(this.tooltipHideTimeout);
                this.showEnglishTooltip(span);
            } else if (this.englishTooltip && !this.englishTooltip.contains(e.target)) {
                this.englishTooltip.classList.remove('visible');
            }
        }, { passive: false });
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
            if (this.englishTooltip) {
                this.englishTooltip.classList.remove('visible');
            }
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

    /**
     * Finds all english-annotations script blocks and wraps annotated words
     * in the corresponding message bodies.
     */
    initializeEnglishAnnotations() {
        const scripts = document.querySelectorAll('script[id^="english-annotations-"]');
        scripts.forEach(script => {
            try {
                const annotations = JSON.parse(script.textContent);
                const messageId = script.id.replace('english-annotations-', '');
                // Find the article containing this script block
                const article = script.closest('article');
                if (!article) return;
                const container = article.querySelector('.message-main');
                if (container) {
                    this.wrapAnnotatedWords(container, annotations);
                }
            } catch (e) {
                // Skip invalid JSON silently
            }
        });
    }

    /**
     * Walks text nodes in the container and wraps matched English words
     * with annotation spans.
     */
    wrapAnnotatedWords(container, annotations) {
        const wordRegex = /[a-zA-Z']+(?:-[a-zA-Z']+)*/g;
        const walker = document.createTreeWalker(
            container,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode(node) {
                    const parent = node.parentElement;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    // Skip elements that should not be annotated
                    if (parent.closest('.literal-text, .annotated-chinese, script, style, .annotated-english, .annotated-stopword, .annotation-inline')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        // Collect text nodes first to avoid modifying DOM during traversal
        const textNodes = [];
        while (walker.nextNode()) {
            textNodes.push(walker.currentNode);
        }

        textNodes.forEach(textNode => {
            const text = textNode.textContent;
            const parts = [];
            let lastIndex = 0;
            let match;

            wordRegex.lastIndex = 0;
            while ((match = wordRegex.exec(text)) !== null) {
                const word = match[0];
                const key = word.toLowerCase();
                const ann = annotations[key];

                if (!ann) {
                    continue;
                }

                // Add text before this match
                if (match.index > lastIndex) {
                    parts.push(document.createTextNode(text.slice(lastIndex, match.index)));
                }

                const span = document.createElement('span');

                if (ann.is_stopword) {
                    span.className = 'annotated-stopword';
                    span.setAttribute('data-pos-category', ann.pos_type || '');
                    span.setAttribute('data-lemma', ann.lemma || '');
                } else {
                    span.className = 'annotated-english';
                    if (ann.guid) span.setAttribute('data-guid', ann.guid);
                    span.setAttribute('data-lemma', ann.lemma || '');
                    if (ann.definition) span.setAttribute('data-definition', ann.definition);
                    if (ann.pos_type) span.setAttribute('data-pos-type', ann.pos_type);
                    if (ann.pos_subtype) span.setAttribute('data-pos-subtype', ann.pos_subtype);
                    if (ann.translations) span.setAttribute('data-translations', JSON.stringify(ann.translations));
                    if (ann.form) span.setAttribute('data-form', ann.form);
                }

                span.textContent = word;
                parts.push(span);
                lastIndex = match.index + word.length;
            }

            if (parts.length === 0) return; // No matches in this text node

            // Add remaining text
            if (lastIndex < text.length) {
                parts.push(document.createTextNode(text.slice(lastIndex)));
            }

            // Replace the text node with the parts
            const fragment = document.createDocumentFragment();
            parts.forEach(p => fragment.appendChild(p));
            textNode.parentNode.replaceChild(fragment, textNode);
        });
    }

    /**
     * Shows the English annotation tooltip for a given annotated span
     */
    showEnglishTooltip(span) {
        const tooltip = this.englishTooltip;
        if (!tooltip) return;

        // Build tooltip content
        if (span.classList.contains('annotated-stopword')) {
            const posCategory = span.getAttribute('data-pos-category') || '';
            const lemma = span.getAttribute('data-lemma') || '';
            tooltip.innerHTML =
                `<span class="lemma-text">${lemma}</span>` +
                ` <span class="pos-type">${posCategory}</span>`;
        } else {
            const lemma = span.getAttribute('data-lemma') || '';
            const definition = span.getAttribute('data-definition') || '';
            const posType = span.getAttribute('data-pos-type') || '';
            const posSubtype = span.getAttribute('data-pos-subtype') || '';
            const guid = span.getAttribute('data-guid') || '';
            const form = span.getAttribute('data-form') || '';
            let translationsHtml = '';

            try {
                const translations = JSON.parse(span.getAttribute('data-translations') || '{}');
                const zhPinyin = translations['zh_pinyin'];
                const entries = Object.entries(translations).filter(([lang]) => lang !== 'zh_pinyin');
                if (entries.length > 0) {
                    translationsHtml = '<span class="translations">' +
                        entries.map(([lang, text]) => {
                            if (lang === 'zh' && zhPinyin) {
                                return `<span class="lang-code">${lang}</span> ${text} <span class="zh-pinyin">(${zhPinyin})</span>`;
                            }
                            return `<span class="lang-code">${lang}</span> ${text}`;
                        }).join(' &middot; ') +
                        '</span>';
                }
            } catch (e) {
                // Skip invalid translations
            }

            const posDisplay = posSubtype ? `${posType} / ${posSubtype}` : posType;
            const formDisplay = form ? ` (${form})` : '';

            tooltip.innerHTML =
                `<span class="lemma-text">${lemma}</span>${formDisplay}` +
                ` <span class="pos-type">${posDisplay}</span>` +
                (definition ? `<span class="definition">${definition}</span>` : '') +
                translationsHtml +
                (guid ? ` <span class="guid">${guid}</span>` : '');
        }

        // Position and show
        this.positionTooltip(span);
        tooltip.classList.add('visible');
    }

    /**
     * Hides the English annotation tooltip after a short delay
     */
    hideEnglishTooltip() {
        this.tooltipHideTimeout = setTimeout(() => {
            if (this.englishTooltip) {
                this.englishTooltip.classList.remove('visible');
            }
        }, 200);
    }

    /**
     * Positions the tooltip relative to the given span element.
     * Places above the word by default; flips below if near the top of the viewport.
     */
    positionTooltip(span) {
        const tooltip = this.englishTooltip;
        if (!tooltip) return;

        // Make visible off-screen first to measure
        tooltip.style.left = '-9999px';
        tooltip.style.top = '-9999px';
        tooltip.classList.add('visible');

        const rect = span.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        const gap = 8;

        // Decide above or below
        const placeAbove = rect.top > tooltipRect.height + gap + 10;

        let top, arrowClass;
        if (placeAbove) {
            top = rect.top + window.scrollY - tooltipRect.height - gap;
            arrowClass = 'arrow-down';
        } else {
            top = rect.bottom + window.scrollY + gap;
            arrowClass = 'arrow-up';
        }

        // Center horizontally on the word, clamp to viewport
        let left = rect.left + window.scrollX + (rect.width / 2) - (tooltipRect.width / 2);
        const viewportPadding = 8;
        const maxLeft = window.scrollX + document.documentElement.clientWidth - tooltipRect.width - viewportPadding;
        left = Math.max(window.scrollX + viewportPadding, Math.min(left, maxLeft));

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
        tooltip.classList.remove('arrow-down', 'arrow-up');
        tooltip.classList.add(arrowClass);
    }

}

// Create a single instance when the DOM is ready
const viewer = new AtacamaViewer();
