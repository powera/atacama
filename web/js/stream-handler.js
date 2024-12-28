// Handle color block expansions
function setupColorBlocks() {
    document.querySelectorAll('[class^="color-"]').forEach(block => {
        const content = block.querySelector('.color-content');
        if (!content) return;

        block.addEventListener('click', (e) => {
            // Don't trigger if clicking on a link inside the content
            if (e.target.tagName === 'A') return;
            
            content.style.display = "block";
        });
    });
}

// Handle Chinese annotations
function setupAnnotations() {
    document.querySelectorAll('.annotated-chinese').forEach(annotation => {
        const pinyin = annotation.getAttribute('data-pinyin');
        const definition = annotation.getAttribute('data-definition');
        
        // Create inline annotation div
        const inlineAnnotation = document.createElement('div');
        inlineAnnotation.className = 'annotation-inline';
        inlineAnnotation.innerHTML = `
            <div class="pinyin">${pinyin}</div>
            <div class="definition">${definition}</div>
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
}

// Initialize both systems when the DOM is ready
function initializeStreamHandlers() {
    setupColorBlocks();
    setupAnnotations();
}

// Set up the handlers when the DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeStreamHandlers);
} else {
    initializeStreamHandlers();
}

// Handle keyboard navigation
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        // Close all expanded elements
        document.querySelectorAll('.color-content.expanded, .annotation-inline.expanded')
            .forEach(el => el.classList.remove('expanded'));
    }
});
