// Create and append the popup container once when the script loads
const popupContainer = document.createElement('div');
popupContainer.className = 'annotation-popup';
document.body.appendChild(popupContainer);

// Create internal popup structure
const popupContent = `
    <div class="pinyin"></div>
    <div class="definition"></div>
    <button class="close-button" aria-label="Close annotation">×</button>
`;
popupContainer.innerHTML = popupContent;

// Get references to popup elements
const pinyinElement = popupContainer.querySelector('.pinyin');
const definitionElement = popupContainer.querySelector('.definition');
const closeButton = popupContainer.querySelector('.close-button');

// Track touch interaction state
let touchStartY = 0;
let currentTranslateY = 0;

// Handle annotation displays
function setupAnnotationSystem() {
    const annotations = document.querySelectorAll('.annotated-chinese');
    
    annotations.forEach(annotation => {
        // Handle both click and touch events
        annotation.addEventListener('click', (event) => {
            event.preventDefault();
            showAnnotation(annotation);
        });
    });

    // Close annotation when clicking outside
    document.addEventListener('click', (event) => {
        if (!event.target.closest('.annotated-chinese') && 
            !event.target.closest('.annotation-popup')) {
            hideAnnotation();
        }
    });

    // Handle swipe to dismiss
    popupContainer.addEventListener('touchstart', (e) => {
        touchStartY = e.touches[0].clientY;
        popupContainer.style.transition = 'none';
    });

    popupContainer.addEventListener('touchmove', (e) => {
        const deltaY = e.touches[0].clientY - touchStartY;
        if (deltaY > 0) { // Only allow downward swipe
            currentTranslateY = deltaY;
            popupContainer.style.transform = `translateY(${deltaY}px)`;
        }
    });

    popupContainer.addEventListener('touchend', (e) => {
        popupContainer.style.transition = 'transform 0.3s ease';
        if (currentTranslateY > 100) { // Threshold for dismiss
            hideAnnotation();
        } else {
            popupContainer.style.transform = 'translateY(0)';
        }
        currentTranslateY = 0;
    });

    // Close button handler
    closeButton.addEventListener('click', hideAnnotation);
}

function showAnnotation(element) {
    const pinyin = element.getAttribute('data-pinyin');
    const definition = element.getAttribute('data-definition');

    // Update popup content
    pinyinElement.textContent = pinyin;
    definitionElement.textContent = definition;

    // Show popup with animation
    popupContainer.style.transform = 'translateY(0)';
    popupContainer.classList.add('active');

    // Add class to currently active annotation
    document.querySelector('.annotation-active')?.classList.remove('annotation-active');
    element.classList.add('annotation-active');

    // Handle keyboard navigation
    closeButton.focus();
}

function hideAnnotation() {
    popupContainer.classList.remove('active');
    popupContainer.style.transform = 'translateY(100%)';
    document.querySelector('.annotation-active')?.classList.remove('annotation-active');
}

// Handle keyboard navigation
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        hideAnnotation();
    }
});

// Initialize the system when the DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupAnnotationSystem);
} else {
    setupAnnotationSystem();
}

// Add necessary styles dynamically
const style = document.createElement('style');
style.textContent = `
    .close-button {
        position: absolute;
        top: var(--spacing-base);
        right: var(--spacing-base);
        width: 44px;
        height: 44px;
        border: none;
        background: none;
        font-size: 24px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #666;
    }

    .annotation-active {
        background-color: rgba(0, 0, 0, 0.05);
        border-radius: var(--border-radius);
    }

    .annotation-popup {
        transform: translateY(100%);
        transition: transform 0.3s ease;
    }

    @media (min-width: 769px) {
        .annotation-popup {
            left: 50%;
            transform: translateX(-50%) translateY(100%);
            max-width: 400px;
            border-radius: var(--border-radius);
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
        }
        
        .annotation-popup.active {
            transform: translateX(-50%) translateY(0);
        }
    }
`;
document.head.appendChild(style);
