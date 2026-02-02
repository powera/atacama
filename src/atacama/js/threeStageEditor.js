/**
 * Three-Stage Blog Post Editor
 *
 * A command-line style editor for composing blog posts incrementally
 * with LLM assistance and public/private version support.
 */
class ThreeStageEditor {
    constructor(draftId) {
        this.draftId = draftId;
        this.MAX_HISTORY = 5;

        // History management (client-side only)
        this.historyStack = [];
        this.historyIndex = -1;

        // Current state
        this.currentContent = '';
        this.currentPreviewVersion = 'private';
        this.currentContentVersion = 'private';
        this.isProcessing = false;
        this.isPublished = false;

        // DOM elements
        this.elements = {};

        // Initialize
        this.initElements();
        this.loadDraft();
        this.bindEvents();
        this.updateUI();
    }

    /**
     * Initialize DOM element references
     */
    initElements() {
        this.elements = {
            // Input section
            userInput: document.getElementById('userInput'),
            targetVersion: document.getElementById('targetVersion'),
            modelSelect: document.getElementById('modelSelect'),
            quickAppend: document.getElementById('quickAppend'),
            aiAppend: document.getElementById('aiAppend'),
            aiCommand: document.getElementById('aiCommand'),
            undoBtn: document.getElementById('undoBtn'),
            redoBtn: document.getElementById('redoBtn'),
            statusText: document.getElementById('statusText'),
            spinner: document.getElementById('spinner'),

            // Content section
            amlContent: document.getElementById('amlContent'),
            wordCount: document.getElementById('wordCount'),
            privateIndicator: document.getElementById('privateIndicator'),
            contentTabs: document.querySelectorAll('.editor-content-section .tab-btn'),

            // Preview section
            previewContent: document.getElementById('previewContent').querySelector('.message-main'),
            previewTabs: document.querySelectorAll('.preview-tab-btn'),
            refreshPreview: document.getElementById('refreshPreview'),

            // Meta section (top)
            subject: document.getElementById('subject'),
            channel: document.getElementById('channel'),
            parentId: document.getElementById('parentId'),

            // Actions
            publishBtn: document.getElementById('publishBtn'),
            saveDraft: document.getElementById('saveDraft')
        };
    }

    /**
     * Bind event handlers
     */
    bindEvents() {
        // Input submission - three buttons
        this.elements.quickAppend.addEventListener('click', () => this.quickAppendInput());
        this.elements.aiAppend.addEventListener('click', () => this.aiAppendInput());
        this.elements.aiCommand.addEventListener('click', () => this.aiCommandInput());

        // Ctrl+Enter = Add (most common action)
        this.elements.userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.quickAppendInput();
            }
        });

        // History navigation
        this.elements.undoBtn.addEventListener('click', () => this.undo());
        this.elements.redoBtn.addEventListener('click', () => this.redo());

        // Keyboard shortcuts for undo/redo
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                if (document.activeElement !== this.elements.amlContent) {
                    e.preventDefault();
                    this.undo();
                }
            }
            if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
                if (document.activeElement !== this.elements.amlContent) {
                    e.preventDefault();
                    this.redo();
                }
            }
        });

        // Content tab switching
        this.elements.contentTabs.forEach(tab => {
            tab.addEventListener('click', (e) => this.switchContentTab(e.target.dataset.tab));
        });

        // Preview tab switching
        this.elements.previewTabs.forEach(tab => {
            tab.addEventListener('click', (e) => this.switchPreviewTab(e.target.dataset.preview));
        });

        // Manual preview refresh
        this.elements.refreshPreview.addEventListener('click', () => this.updatePreview());

        // Manual content edits
        this.elements.amlContent.addEventListener('input', () => {
            this.handleManualEdit();
        });

        // Publish and save buttons
        this.elements.publishBtn.addEventListener('click', () => this.publish());
        this.elements.saveDraft.addEventListener('click', () => this.saveDraftToStorage());

        // Warn before leaving with unsaved changes
        window.addEventListener('beforeunload', (e) => {
            if (this.hasUnsavedChanges()) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    }

    /**
     * Load draft from localStorage
     */
    loadDraft() {
        const storageKey = `draft_${this.draftId}`;
        const saved = localStorage.getItem(storageKey);

        if (saved) {
            try {
                const data = JSON.parse(saved);
                this.currentContent = data.content || '';
                this.elements.amlContent.value = this.currentContent;
                this.elements.subject.value = data.subject || '';
                this.elements.channel.value = data.channel || this.elements.channel.value;
                this.elements.parentId.value = data.parentId || '';

                // Restore history if available
                if (data.history) {
                    this.historyStack = data.history;
                    this.historyIndex = data.historyIndex || this.historyStack.length - 1;
                }

                this.setStatus('Draft loaded');
            } catch (e) {
                console.error('Error loading draft:', e);
                this.setStatus('Error loading draft');
            }
        } else {
            // New draft - add initial empty state to history
            this.pushHistory('');
        }

        this.updateUI();
        this.updatePreview();
    }

    /**
     * Save draft to localStorage
     */
    saveDraftToStorage(silent = false) {
        const storageKey = `draft_${this.draftId}`;
        const data = {
            content: this.currentContent,
            subject: this.elements.subject.value,
            channel: this.elements.channel.value,
            parentId: this.elements.parentId.value,
            history: this.historyStack,
            historyIndex: this.historyIndex,
            lastSaved: new Date().toISOString()
        };

        localStorage.setItem(storageKey, JSON.stringify(data));

        if (!silent) {
            this.setStatus('Draft saved');
        }
    }

    /**
     * Check for unsaved changes
     */
    hasUnsavedChanges() {
        // No warning needed after successful publish
        if (this.isPublished) {
            return false;
        }

        const storageKey = `draft_${this.draftId}`;
        const saved = localStorage.getItem(storageKey);

        if (!saved) {
            return this.currentContent.trim().length > 0;
        }

        try {
            const data = JSON.parse(saved);
            return data.content !== this.currentContent;
        } catch {
            return true;
        }
    }

    /**
     * Quick append - add text exactly as typed (no LLM)
     */
    quickAppendInput() {
        const input = this.elements.userInput.value.trim();
        if (!input || this.isProcessing) return;

        // Save to history before applying
        this.pushHistory(this.currentContent);

        // Concatenate directly
        let separator = '';
        if (this.currentContent && !this.currentContent.endsWith('\n')) {
            separator = '\n\n';
        } else if (this.currentContent) {
            separator = '\n';
        }

        // Wrap in private markers if target is private
        let textToAdd = input;
        if (this.elements.targetVersion.value === 'private') {
            if (input.includes('\n')) {
                textToAdd = `<<<PRIVATE: ${input} >>>`;
            } else {
                textToAdd = `<<PRIVATE: ${input} >>`;
            }
        }

        this.currentContent = this.currentContent + separator + textToAdd;
        this.elements.amlContent.value = this.currentContent;
        this.elements.userInput.value = '';

        this.updateUI();
        this.updatePreview();
        this.saveDraftToStorage(true);
        this.setStatus('Added');
    }

    /**
     * AI Append - LLM generates new content, we concatenate (preserves existing)
     */
    async aiAppendInput() {
        const input = this.elements.userInput.value.trim();
        if (!input || this.isProcessing) return;

        this.setProcessing(true);
        this.setStatus('AI generating...');

        try {
            const response = await fetch(`/api/editor/${this.draftId}/ai-append`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    input: input,
                    current_content: this.currentContent,
                    target_version: this.elements.targetVersion.value,
                    model: this.elements.modelSelect.value
                })
            });

            const result = await response.json();

            if (result.success) {
                this.pushHistory(this.currentContent);
                this.currentContent = result.new_content;
                this.elements.amlContent.value = this.currentContent;
                this.elements.userInput.value = '';
                this.updateUI();
                this.updatePreview();
                this.saveDraftToStorage(true);
                this.setStatus(result.summary || 'AI content added');
            } else {
                this.setStatus(`Error: ${result.error}`);
            }
        } catch (error) {
            console.error('Error in AI append:', error);
            this.setStatus(`Error: ${error.message}`);
        } finally {
            this.setProcessing(false);
        }
    }

    /**
     * AI Command - LLM executes command (may rewrite entire content)
     */
    async aiCommandInput() {
        const input = this.elements.userInput.value.trim();
        if (!input || this.isProcessing) return;

        this.setProcessing(true);
        this.setStatus('AI processing...');

        try {
            const response = await fetch(`/api/editor/${this.draftId}/ai-command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    input: input,
                    current_content: this.currentContent,
                    target_version: this.elements.targetVersion.value,
                    model: this.elements.modelSelect.value
                })
            });

            const result = await response.json();

            if (result.success) {
                this.pushHistory(this.currentContent);
                this.currentContent = result.new_content;
                this.elements.amlContent.value = this.currentContent;
                this.elements.userInput.value = '';
                this.updateUI();
                this.updatePreview();
                this.saveDraftToStorage(true);
                this.setStatus(result.summary || 'Command executed');
            } else {
                this.setStatus(`Error: ${result.error}`);
            }
        } catch (error) {
            console.error('Error in AI command:', error);
            this.setStatus(`Error: ${error.message}`);
        } finally {
            this.setProcessing(false);
        }
    }


    /**
     * Handle manual edits to the content area
     */
    handleManualEdit() {
        const newContent = this.elements.amlContent.value;

        // Only track significant changes
        if (newContent !== this.currentContent) {
            this.currentContent = newContent;
            this.updateUI();

            // Debounced preview update
            if (this.previewTimeout) clearTimeout(this.previewTimeout);
            this.previewTimeout = setTimeout(() => this.updatePreview(), 500);
        }
    }

    /**
     * Push content to history stack
     */
    pushHistory(content) {
        // Remove any redo history
        this.historyStack = this.historyStack.slice(0, this.historyIndex + 1);

        // Add new state
        this.historyStack.push(content);

        // Limit history size
        if (this.historyStack.length > this.MAX_HISTORY) {
            this.historyStack.shift();
        }

        this.historyIndex = this.historyStack.length - 1;
        this.updateHistoryButtons();
    }

    /**
     * Undo to previous state
     */
    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            this.currentContent = this.historyStack[this.historyIndex];
            this.elements.amlContent.value = this.currentContent;
            this.updateUI();
            this.updatePreview();
            this.saveDraftToStorage(true);
            this.setStatus('Undone');
        }
    }

    /**
     * Redo to next state
     */
    redo() {
        if (this.historyIndex < this.historyStack.length - 1) {
            this.historyIndex++;
            this.currentContent = this.historyStack[this.historyIndex];
            this.elements.amlContent.value = this.currentContent;
            this.updateUI();
            this.updatePreview();
            this.saveDraftToStorage(true);
            this.setStatus('Redone');
        }
    }

    /**
     * Update history button states
     */
    updateHistoryButtons() {
        this.elements.undoBtn.disabled = this.historyIndex <= 0;
        this.elements.redoBtn.disabled = this.historyIndex >= this.historyStack.length - 1;
    }

    /**
     * Switch content view tab (private/public)
     */
    switchContentTab(version) {
        this.currentContentVersion = version;

        // Update tab active states
        this.elements.contentTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === version);
        });

        // For content view, we always show the full content with visual styling
        // The "public" view just filters what's shown in the textarea
        if (version === 'public') {
            // Show public-only content (strip private markers)
            this.updateContentViewForPublic();
        } else {
            // Show full content
            this.elements.amlContent.value = this.currentContent;
        }
    }

    /**
     * Update content view to show public-only version
     */
    async updateContentViewForPublic() {
        try {
            const response = await fetch('/api/editor/check-private', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: this.currentContent
                })
            });

            const result = await response.json();

            // For now, just add visual styling
            // A more sophisticated implementation would filter content
            if (result.has_private) {
                this.elements.amlContent.classList.add('public-view');
            } else {
                this.elements.amlContent.classList.remove('public-view');
            }
        } catch (error) {
            console.error('Error checking private content:', error);
        }
    }

    /**
     * Switch preview tab (private/public)
     */
    switchPreviewTab(version) {
        this.currentPreviewVersion = version;

        // Update tab active states
        this.elements.previewTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.preview === version);
        });

        // Refresh preview with new version
        this.updatePreview();
    }

    /**
     * Update the rendered preview
     */
    async updatePreview() {
        try {
            const response = await fetch(`/api/editor/${this.draftId}/preview`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: this.currentContent,
                    version: this.currentPreviewVersion
                })
            });

            const result = await response.json();

            if (result.success) {
                this.elements.previewContent.innerHTML = result.html;

                // Initialize Atacama viewer for dynamic content
                if (typeof AtacamaViewer !== 'undefined') {
                    const viewer = new AtacamaViewer();
                    viewer.initialize();
                }
            } else {
                this.elements.previewContent.innerHTML = `<p class="error">Preview error: ${result.error}</p>`;
            }
        } catch (error) {
            console.error('Error updating preview:', error);
            this.elements.previewContent.innerHTML = `<p class="error">Preview error: ${error.message}</p>`;
        }
    }

    /**
     * Publish the draft
     */
    async publish() {
        const subject = this.elements.subject.value.trim();
        const content = this.currentContent.trim();

        if (!subject) {
            this.setStatus('Subject is required');
            this.elements.subject.focus();
            return;
        }

        if (!content) {
            this.setStatus('Content is required');
            return;
        }

        this.setProcessing(true);
        this.setStatus('Publishing...');

        try {
            const response = await fetch(`/api/editor/${this.draftId}/publish`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    subject: subject,
                    content: content,
                    channel: this.elements.channel.value,
                    parent_id: this.elements.parentId.value || null
                })
            });

            const result = await response.json();

            if (result.success) {
                // Mark as published to prevent beforeunload warning
                this.isPublished = true;

                // Clear draft from storage
                localStorage.removeItem(`draft_${this.draftId}`);

                // Redirect to the new message
                window.location.href = result.message_url;
            } else {
                this.setStatus(`Publish error: ${result.error}`);
            }
        } catch (error) {
            console.error('Error publishing:', error);
            this.setStatus(`Publish error: ${error.message}`);
        } finally {
            this.setProcessing(false);
        }
    }

    /**
     * Update UI state
     */
    updateUI() {
        // Update word count
        const words = this.currentContent.trim().split(/\s+/).filter(w => w.length > 0);
        this.elements.wordCount.textContent = `${words.length} words`;

        // Check for private content
        this.checkPrivateContent();

        // Update history buttons
        this.updateHistoryButtons();
    }

    /**
     * Check if content contains private markers
     */
    async checkPrivateContent() {
        if (!this.currentContent) {
            this.elements.privateIndicator.classList.add('hidden');
            return;
        }

        try {
            const response = await fetch('/api/editor/check-private', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: this.currentContent
                })
            });

            const result = await response.json();
            this.elements.privateIndicator.classList.toggle('hidden', !result.has_private);
        } catch (error) {
            console.error('Error checking private content:', error);
        }
    }

    /**
     * Set processing state
     */
    setProcessing(processing) {
        this.isProcessing = processing;
        this.elements.quickAppend.disabled = processing;
        this.elements.aiAppend.disabled = processing;
        this.elements.aiCommand.disabled = processing;
        this.elements.spinner.classList.toggle('hidden', !processing);
    }

    /**
     * Set status message
     */
    setStatus(message) {
        this.elements.statusText.textContent = message;
    }
}

// Export for global access
window.ThreeStageEditor = ThreeStageEditor;
