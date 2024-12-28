// Combined handler for annotations, stream interactions, and tooltips
class AtacamaHandlers {
    constructor() {
        this.setupAnnotationPopup();
        this.setupTooltipContainer();
        this.bindEvents();
        this.currentAnnotation = null;
        this.touchStartY = 0;
        this.currentTranslateY = 0;
    }

    setupAnnotationPopup() {
        this.popup = document.createElement('div');
        this.popup.className = 'annotation-popup';
        this.popup.innerHTML = `
            <span class="pinyin"></span>
            <span class="definition"></span>
            <button class="close-button" aria-label="Close annotation">×</button>
        `;
        document.body.appendChild(this.popup);

        this.pinyinEl = this.popup.querySelector('.pinyin');
        this.definitionEl = this.popup.querySelector('.definition');
        this.closeButton = this.popup.querySelector('.close-button');
    }

    setupTooltipContainer() {
        this.tooltipContainer = document.createElement('div');
        this.tooltipContainer.className = 'tooltip';
        document.body.appendChild(this.tooltipContainer);
    }

    bindEvents() {
        // Annotation click handlers
        document.addEventListener('click', (e) => {
            const annotation = e.target.closest('.annotated-chinese');
            if (annotation) {
                e.preventDefault();
                this.showAnnotation(annotation);
            } else if (!e.target.closest('.annotation-popup')) {
                this.hideAnnotation();
            }
        });

        // Close button handler
        this.closeButton.addEventListener('click', () => this.hideAnnotation());

        // Touch events for swipe dismissal
        this.popup.addEventListener('touchstart', (e) => {
            this.touchStartY = e.touches[0].clientY;
            this.popup.style.transition = 'none';
        });

        this.popup.addEventListener('touchmove', (e) => {
            const deltaY = e.touches[0].clientY - this.touchStartY;
            if (deltaY > 0) {
                this.currentTranslateY = deltaY;
                this.popup.style.transform = `translateY(${deltaY}px)`;
            }
        });

        this.popup.addEventListener('touchend', () => {
            this.popup.style.transition = 'transform 0.3s ease';
            if (this.currentTranslateY > 100) {
                this.hideAnnotation();
            } else {
                this.popup.style.transform = 'translateY(0)';
            }
            this.currentTranslateY = 0;
        });

        // Handle LLM annotations
        document.querySelectorAll('.llm-annotation').forEach(el => {
            el.addEventListener('mouseover', e => {
                this.tooltipContainer.textContent = e.target.getAttribute('data-type');
                this.tooltipContainer.classList.add('visible');
                
                const rect = e.target.getBoundingClientRect();
                this.tooltipContainer.style.left = rect.left + 'px';
                this.tooltipContainer.style.top = (rect.top - this.tooltipContainer.offsetHeight - 5) + 'px';
            });
            
            el.addEventListener('mouseout', () => {
                this.tooltipContainer.classList.remove('visible');
            });
        });

        // Handle color block expansions
        document.querySelectorAll('[class^="color-"]').forEach(block => {
            const content = block.querySelector('.colortext-content');
            const sigil = block.querySelector('.sigil');
            if (!content) return;

            sigil.addEventListener('click', (e) => {
                // Don't trigger if clicking on a link inside the content
                if (e.target.tagName === 'A') return;
                
                content.classList.toggle('expanded');
            });
        });

        // Handle Chinese annotations
        document.querySelectorAll('.annotated-chinese').forEach(annotation => {
            const pinyin = annotation.getAttribute('data-pinyin');
            const definition = annotation.getAttribute('data-definition');
            
            // Create inline annotation div
            const inlineAnnotation = document.createElement('div');
            inlineAnnotation.className = 'annotation-inline';
            inlineAnnotation.innerHTML = `
                <span class="pinyin">${pinyin}</span>
                <span class="definition">${definition}</span>
            `;
            
            // Insert after the annotation
            annotation.parentNode.insertBefore(inlineAnnotation, annotation.nextSibling);
            
            annotation.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                // Close any other open annotations
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
                this.hideAnnotation();
                // Close all expanded elements
                document.querySelectorAll('.colortext-content.expanded, .annotation-inline.expanded')
                    .forEach(el => el.classList.remove('expanded'));
            }
        });
    }

    showAnnotation(element) {
        const pinyin = element.getAttribute('data-pinyin');
        const definition = element.getAttribute('data-definition');

        if (!pinyin || !definition) {
            console.warn('Missing annotation data:', { pinyin, definition });
            return;
        }

        this.pinyinEl.textContent = pinyin;
        this.definitionEl.textContent = definition;
        
        this.popup.classList.add('active');
        
        if (this.currentAnnotation) {
            this.currentAnnotation.classList.remove('annotation-active');
        }
        
        element.classList.add('annotation-active');
        this.currentAnnotation = element;
        
        this.closeButton.focus();
    }

    hideAnnotation() {
        this.popup.classList.remove('active');
        if (this.currentAnnotation) {
            this.currentAnnotation.classList.remove('annotation-active');
            this.currentAnnotation = null;
        }
    }
}

// Helper function for print mode
function preparePrint() {
    window.print();
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new AtacamaHandlers());
} else {
    new AtacamaHandlers();
}
