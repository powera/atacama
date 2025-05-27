/**
 * Diff utility for comparing code versions
 * Provides line-by-line diff functionality with LCS-based algorithm
 */

class DiffUtil {
    /**
     * Generate diff between two text strings
     * @param {string} originalText - Original text
     * @param {string} improvedText - Improved text
     * @returns {Array} Array of diff objects
     */
    static generateDiff(originalText, improvedText) {
        // Handle empty inputs
        if (!originalText && !improvedText) {
            return [];
        }
        
        const originalLines = (originalText || '').split('\n');
        const improvedLines = (improvedText || '').split('\n');
        
        // Compute line-by-line diff using improved LCS algorithm
        const diff = this.computeLineDiff(originalLines, improvedLines);
        
        return diff;
    }

    /**
     * Compute line-by-line diff using improved Myers diff algorithm
     * @param {Array} originalLines - Original lines array
     * @param {Array} improvedLines - Improved lines array
     * @returns {Array} Diff result
     */
    static computeLineDiff(originalLines, improvedLines) {
        const diff = [];
        
        // Handle empty arrays
        if (originalLines.length === 0 && improvedLines.length === 0) {
            return diff;
        }
        
        // Use improved algorithm that processes changes in order
        const lcsMatrix = this.computeLCSMatrix(originalLines, improvedLines);
        
        // Backtrack through the matrix to build the diff
        let i = originalLines.length;
        let j = improvedLines.length;
        const result = [];
        
        while (i > 0 || j > 0) {
            if (i > 0 && j > 0 && originalLines[i - 1] === improvedLines[j - 1]) {
                // Lines match - add to front of result
                result.unshift({
                    type: 'unchanged',
                    original: originalLines[i - 1],
                    improved: improvedLines[j - 1],
                    originalLineNum: i,
                    improvedLineNum: j
                });
                i--;
                j--;
            } else if (j > 0 && (i === 0 || lcsMatrix[i][j - 1] >= lcsMatrix[i - 1][j])) {
                // Addition
                result.unshift({
                    type: 'added',
                    improved: improvedLines[j - 1],
                    improvedLineNum: j
                });
                j--;
            } else if (i > 0) {
                // Deletion
                result.unshift({
                    type: 'removed',
                    original: originalLines[i - 1],
                    originalLineNum: i
                });
                i--;
            }
        }
        
        return result;
    }

    /**
     * Compute LCS length matrix using dynamic programming
     * @param {Array} a - First array
     * @param {Array} b - Second array
     * @returns {Array} LCS length matrix
     */
    static computeLCSMatrix(a, b) {
        const m = a.length;
        const n = b.length;
        
        // Create DP table
        const dp = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0));
        
        // Build LCS length table
        for (let i = 1; i <= m; i++) {
            for (let j = 1; j <= n; j++) {
                if (a[i - 1] === b[j - 1]) {
                    dp[i][j] = dp[i - 1][j - 1] + 1;
                } else {
                    dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
                }
            }
        }
        
        return dp;
    }

    /**
     * Improved LCS computation using dynamic programming with proper backtracking
     * @param {Array} a - First array
     * @param {Array} b - Second array
     * @returns {Array} Longest common subsequence
     */
    static computeLCS(a, b) {
        const m = a.length;
        const n = b.length;
        
        if (m === 0 || n === 0) {
            return [];
        }
        
        // Get the LCS matrix
        const dp = this.computeLCSMatrix(a, b);
        
        // Reconstruct LCS using backtracking
        const lcs = [];
        let i = m, j = n;
        
        while (i > 0 && j > 0) {
            if (a[i - 1] === b[j - 1]) {
                lcs.unshift(a[i - 1]);
                i--;
                j--;
            } else if (dp[i - 1][j] > dp[i][j - 1]) {
                i--;
            } else {
                j--;
            }
        }
        
        return lcs;
    }

    /**
     * Create aligned diff for side-by-side display
     * @param {Array} diff - Diff array
     * @returns {Array} Aligned diff
     */
    static createAlignedDiff(diff) {
        const aligned = [];
        
        diff.forEach(item => {
            if (item.type === 'unchanged') {
                aligned.push({
                    original: {
                        content: item.original,
                        lineNum: item.originalLineNum,
                        type: 'unchanged'
                    },
                    improved: {
                        content: item.improved,
                        lineNum: item.improvedLineNum,
                        type: 'unchanged'
                    }
                });
            } else if (item.type === 'removed') {
                aligned.push({
                    original: {
                        content: item.original,
                        lineNum: item.originalLineNum,
                        type: 'removed'
                    },
                    improved: null
                });
            } else if (item.type === 'added') {
                aligned.push({
                    original: null,
                    improved: {
                        content: item.improved,
                        lineNum: item.improvedLineNum,
                        type: 'added'
                    }
                });
            }
        });
        
        return aligned;
    }

    /**
     * Update side-by-side diff view
     * @param {Array} diff - Diff array
     */
    static updateSideBySideView(diff) {
        const originalLineNumbers = document.getElementById('original-line-numbers');
        const originalCodeContent = document.getElementById('original-code-content');
        const improvedLineNumbers = document.getElementById('improved-line-numbers');
        const improvedCodeContent = document.getElementById('improved-code-content');
        
        // Check if elements exist
        if (!originalLineNumbers || !originalCodeContent || !improvedLineNumbers || !improvedCodeContent) {
            console.error('Required diff view elements not found');
            return;
        }
        
        let originalHTML = '';
        let improvedHTML = '';
        let originalLineNumHTML = '';
        let improvedLineNumHTML = '';
        
        // Process diff to create aligned rows
        const alignedDiff = this.createAlignedDiff(diff);
        
        alignedDiff.forEach(row => {
            // Original side
            if (row.original) {
                const originalClass = row.original.type === 'removed' ? 'line-removed' : '';
                const lineNum = this.escapeHtml(String(row.original.lineNum || ''));
                originalLineNumHTML += `<div class="line-num ${originalClass}">${lineNum}</div>`;
                originalHTML += `<div class="code-line ${originalClass}">${this.escapeHtml(row.original.content || '')}</div>`;
            } else {
                originalLineNumHTML += `<div class="line-num line-empty"></div>`;
                originalHTML += `<div class="code-line line-empty"></div>`;
            }
            
            // Improved side
            if (row.improved) {
                const improvedClass = row.improved.type === 'added' ? 'line-added' : '';
                const lineNum = this.escapeHtml(String(row.improved.lineNum || ''));
                improvedLineNumHTML += `<div class="line-num ${improvedClass}">${lineNum}</div>`;
                improvedHTML += `<div class="code-line ${improvedClass}">${this.escapeHtml(row.improved.content || '')}</div>`;
            } else {
                improvedLineNumHTML += `<div class="line-num line-empty"></div>`;
                improvedHTML += `<div class="code-line line-empty"></div>`;
            }
        });
        
        originalLineNumbers.innerHTML = originalLineNumHTML;
        originalCodeContent.innerHTML = originalHTML;
        improvedLineNumbers.innerHTML = improvedLineNumHTML;
        improvedCodeContent.innerHTML = improvedHTML;
        
        // Update line counts
        const originalLines = alignedDiff.filter(row => row.original && row.original.content !== undefined).length;
        const improvedLines = alignedDiff.filter(row => row.improved && row.improved.content !== undefined).length;
        
        const originalLineCount = document.getElementById('original-line-count');
        const improvedLineCount = document.getElementById('improved-line-count');
        
        if (originalLineCount) originalLineCount.textContent = `${originalLines} lines`;
        if (improvedLineCount) improvedLineCount.textContent = `${improvedLines} lines`;
        
        // Setup synchronized scrolling
        this.setupScrollSync();
    }

    /**
     * Update unified diff view
     * @param {Array} diff - Diff array
     */
    static updateUnifiedView(diff) {
        const unifiedLineNumbers = document.getElementById('unified-line-numbers');
        const unifiedCodeContent = document.getElementById('unified-code-content');
        
        // Check if elements exist
        if (!unifiedLineNumbers || !unifiedCodeContent) {
            console.error('Required unified view elements not found');
            return;
        }
        
        let unifiedHTML = '';
        let lineNumHTML = '';
        let lineNum = 1;
        
        diff.forEach(item => {
            if (item.type === 'unchanged') {
                lineNumHTML += `<div class="line-num">${this.escapeHtml(String(lineNum))}</div>`;
                unifiedHTML += `<div class="code-line">${this.escapeHtml(item.original)}</div>`;
                lineNum++;
            } else if (item.type === 'removed') {
                lineNumHTML += `<div class="line-num line-removed">-</div>`;
                unifiedHTML += `<div class="code-line line-removed">- ${this.escapeHtml(item.original)}</div>`;
            } else if (item.type === 'added') {
                lineNumHTML += `<div class="line-num line-added">+</div>`;
                unifiedHTML += `<div class="code-line line-added">+ ${this.escapeHtml(item.improved)}</div>`;
                lineNum++;
            }
        });
        
        unifiedLineNumbers.innerHTML = lineNumHTML;
        unifiedCodeContent.innerHTML = unifiedHTML;
    }

    /**
     * Setup synchronized scrolling between diff panels
     */
    static setupScrollSync() {
        const originalContent = document.getElementById('original-code-content');
        const improvedContent = document.getElementById('improved-code-content');
        
        if (!originalContent || !improvedContent) return;
        
        let syncing = false;
        
        const syncScroll = (source, target) => {
            if (syncing) return;
            syncing = true;
            
            const scrollPercentage = source.scrollTop / (source.scrollHeight - source.clientHeight);
            target.scrollTop = scrollPercentage * (target.scrollHeight - target.clientHeight);
            
            setTimeout(() => { syncing = false; }, 50);
        };
        
        // Remove existing listeners to prevent duplicates
        const newOriginal = originalContent.cloneNode(true);
        const newImproved = improvedContent.cloneNode(true);
        originalContent.parentNode.replaceChild(newOriginal, originalContent);
        improvedContent.parentNode.replaceChild(newImproved, improvedContent);
        
        // Add scroll listeners
        newOriginal.addEventListener('scroll', () => syncScroll(newOriginal, newImproved));
        newImproved.addEventListener('scroll', () => syncScroll(newImproved, newOriginal));
    }

    /**
     * Update diff statistics
     * @param {Array} diff - Diff array
     */
    static updateDiffStats(diff) {
        const added = diff.filter(d => d.type === 'added').length;
        const removed = diff.filter(d => d.type === 'removed').length;
        const unchanged = diff.filter(d => d.type === 'unchanged').length;
        
        const statsElement = document.getElementById('diff-stats-text');
        if (statsElement) {
            statsElement.innerHTML = `
                <span class="stat-added">+${added}</span> 
                <span class="stat-removed">-${removed}</span> 
                <span class="stat-unchanged">${unchanged} unchanged</span>
            `;
        }
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    /**
     * Toggle between side-by-side and unified diff views
     */
    static toggleDiffMode() {
        const sideBySide = document.getElementById('side-by-side-view');
        const unified = document.getElementById('unified-view');
        const modeText = document.getElementById('diff-mode-text');
        
        if (!sideBySide || !unified || !modeText) {
            console.error('Required view elements not found');
            return;
        }
        
        if (sideBySide.classList.contains('active')) {
            sideBySide.classList.remove('active');
            unified.classList.add('active');
            modeText.textContent = 'Switch to Side-by-Side';
        } else {
            unified.classList.remove('active');
            sideBySide.classList.add('active');
            modeText.textContent = 'Switch to Unified View';
        }
    }
}

// Export for use in other scripts
window.DiffUtil = DiffUtil;