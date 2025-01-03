// Combined handler for annotations, stream interactions
class AtacamaHandlers {
    constructor() {
        this.bindEvents();
        this.currentAnnotation = null;
        this.touchStartY = 0;
        this.currentTranslateY = 0;
    }

    bindEvents() {
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new AtacamaHandlers());
} else {
    new AtacamaHandlers();
}
