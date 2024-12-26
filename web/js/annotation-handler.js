// annotation-handler.js
class AnnotationHandler {
    constructor() {
        this.setupPopup();
        this.bindEvents();
        this.currentAnnotation = null;
        this.touchStartY = 0;
        this.currentTranslateY = 0;
    }

    setupPopup() {
        this.popup = document.createElement('div');
        this.popup.className = 'annotation-popup';
        this.popup.innerHTML = `
            <div class="pinyin"></div>
            <div class="definition"></div>
            <button class="close-button" aria-label="Close annotation">×</button>
        `;
        document.body.appendChild(this.popup);

        this.pinyinEl = this.popup.querySelector('.pinyin');
        this.definitionEl = this.popup.querySelector('.definition');
        this.closeButton = this.popup.querySelector('.close-button');
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

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideAnnotation();
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new AnnotationHandler());
} else {
    new AnnotationHandler();
}