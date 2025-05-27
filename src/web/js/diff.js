
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
        const originalLines = originalText.split('\n');
        const improvedLines = improvedText.split('\n');
        
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
        // Use improved Myers diff algorithm with better LCS computation
        const lcs = this.computeLCS(originalLines, improvedLines);
        const diff = [];
        
        let originalIndex = 0;
        let improvedIndex = 0;
        let lcsIndex = 0;
        
        while (originalIndex < originalLines.length || improvedIndex < improvedLines.length) {
            // Check if we're at an LCS match
            if (lcsIndex < lcs.length && 
                originalIndex < originalLines.length && 
                improvedIndex < improvedLines.length &&
                originalLines[originalIndex] === lcs[lcsIndex] &&
                improvedLines[improvedIndex] === lcs[lcsIndex]) {
                
                // This line is unchanged
                diff.push({
                    type: 'unchanged',
                    original: originalLines[originalIndex],
                    improved: improvedLines[improvedIndex],
                    originalLineNum: originalIndex + 1,
                    improvedLineNum: improvedIndex + 1
                });
                originalIndex++;
                improvedIndex++;
                lcsIndex++;
            } else {
                // Handle deletions first
                while (originalIndex < originalLines.length && 
                       (lcsIndex >= lcs.length || originalLines[originalIndex] !== lcs[lcsIndex])) {
                    diff.push({
                        type: 'removed',
                        original: originalLines[originalIndex],
                        originalLineNum: originalIndex + 1
                    });
                    originalIndex++;
                }
                
                // Then handle additions
                while (improvedIndex < improvedLines.length && 
                       (lcsIndex >= lcs.length || improvedLines[improvedIndex] !== lcs[lcsIndex])) {
                    diff.push({
                        type: 'added',
                        improved: improvedLines[improvedIndex],
                        improvedLineNum: improvedIndex + 1
                    });
                    improvedIndex++;
                }
            }
        }
        
        return diff;
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
                originalLineNumHTML += `<div class="line-num ${originalClass}">${row.original.lineNum || ''}</div>`;
                originalHTML += `<div class="code-line ${originalClass}">${this.escapeHtml(row.original.content || '')}</div>`;
            } else {
                originalLineNumHTML += `<div class="line-num line-empty"></div>`;
                originalHTML += `<div class="code-line line-empty"></div>`;
            }
            
            // Improved side
            if (row.improved) {
                const improvedClass = row.improved.type === 'added' ? 'line-added' : '';
                improvedLineNumHTML += `<div class="line-num ${improvedClass}">${row.improved.lineNum || ''}</div>`;
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
        const originalLines = alignedDiff.filter(row => row.original && row.original.content).length;
        const improvedLines = alignedDiff.filter(row => row.improved && row.improved.content).length;
        document.getElementById('original-line-count').textContent = `${originalLines} lines`;
        document.getElementById('improved-line-count').textContent = `${improvedLines} lines`;
    }

    /**
     * Update unified diff view
     * @param {Array} diff - Diff array
     */
    static updateUnifiedView(diff) {
        const unifiedLineNumbers = document.getElementById('unified-line-numbers');
        const unifiedCodeContent = document.getElementById('unified-code-content');
        
        let unifiedHTML = '';
        let lineNumHTML = '';
        let lineNum = 1;
        
        diff.forEach(item => {
            if (item.type === 'unchanged') {
                lineNumHTML += `<div class="line-num">${lineNum}</div>`;
                unifiedHTML += `<div class="code-line">${this.escapeHtml(item.original)}</div>`;
                lineNum++;
            } else if (item.type === 'removed') {
                lineNumHTML += `<div class="line-num line-removed">-</div>`;
                unifiedHTML += `<div class="code-line line-removed">- ${this.escapeHtml(item.original)}</div>`;
            } else if (item.type === 'added') {
                lineNumHTML += `<div class="line-num line-added">+</div>`;
                unifiedHTML += `<div class="code-line line-added">+ ${this.escapeHtml(item.improved)}</div>`;
            }
        });
        
        unifiedLineNumbers.innerHTML = lineNumHTML;
        unifiedCodeContent.innerHTML = unifiedHTML;
    }

    /**
     * Update diff statistics
     * @param {Array} diff - Diff array
     */
    static updateDiffStats(diff) {
        const added = diff.filter(d => d.type === 'added').length;
        const removed = diff.filter(d => d.type === 'removed').length;
        const unchanged = diff.filter(d => d.type === 'unchanged').length;
        
        document.getElementById('diff-stats-text').innerHTML = `
            <span class="stat-added">+${added}</span> 
            <span class="stat-removed">-${removed}</span> 
            <span class="stat-unchanged">${unchanged} unchanged</span>
        `;
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Toggle between side-by-side and unified diff views
     */
    static toggleDiffMode() {
        const sideBySide = document.getElementById('side-by-side-view');
        const unified = document.getElementById('unified-view');
        const modeText = document.getElementById('diff-mode-text');
        
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
