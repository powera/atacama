// Handle tooltip positioning
document.addEventListener('DOMContentLoaded', function() {
    const tooltipContainer = document.createElement('div');
    tooltipContainer.className = 'tooltip';
    document.body.appendChild(tooltipContainer);

    // Handle LLM annotations
    document.querySelectorAll('.llm-annotation').forEach(el => {
        el.addEventListener('mouseover', e => {
            tooltipContainer.textContent = e.target.getAttribute('data-type');
            tooltipContainer.classList.add('visible');
            
            const rect = e.target.getBoundingClientRect();
            tooltipContainer.style.left = rect.left + 'px';
            tooltipContainer.style.top = (rect.top - tooltipContainer.offsetHeight - 5) + 'px';
        });
        
        el.addEventListener('mouseout', () => {
            tooltipContainer.classList.remove('visible');
        });
    });
});

// Handle print mode
function preparePrint() {
    window.print();
}