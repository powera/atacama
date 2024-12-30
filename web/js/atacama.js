// Combined handler for annotations, stream interactions, and tooltips
class AtacamaHandlers {
    constructor() {
        this.setupTooltipContainer();
        this.bindEvents();
        this.currentAnnotation = null;
        this.touchStartY = 0;
        this.currentTranslateY = 0;
    }

    setupTooltipContainer() {
        this.tooltipContainer = document.createElement('div');
        this.tooltipContainer.className = 'tooltip';
        document.body.appendChild(this.tooltipContainer);
    }

    bindEvents() {
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
