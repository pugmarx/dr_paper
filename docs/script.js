// ==============================================================================
// Dr. Paper: Frontend Web Client (The Morning Paper Research Journal)
// Live PostgREST integration with Supabase (status='published')
// Cross-Device Reading State (Unread Queue, Saved, Starred, Touch Gestures)
// ==============================================================================

const SUPABASE_CONFIG = {
    url: "https://fmwuhpmhgjcoxgevjyxo.supabase.co",
    anonKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZtd3VocG1oZ2pjb3hnZXZqeXhvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc0OTMwNjAsImV4cCI6MjEwMzA2OTA2MH0.gsg3IhbtyYmOXagrnZ5mZ13KOzw39BOZHtyG-mzNmYw",
    schema: "dr_paper"
};

function renderMarkdownToHtml(mdText) {
    if (!mdText) return '';
    let html = mdText
        .replace(/^### (.*$)/gim, '<h3 class="section-heading">$1</h3>')
        .replace(/^## (.*$)/gim, '<h3 class="section-heading">$1</h3>')
        .replace(/^> (.*$)/gim, '<blockquote class="essay-quote">$1</blockquote>')
        .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/gim, '<em>$1</em>')
        .replace(/`([^`]+)`/gim, '<code>$1</code>');
    
    const blocks = html.split(/\n\s*\n/).map(p => {
        p = p.trim();
        if (!p) return '';
        if (p.startsWith('<h3') || p.startsWith('<blockquote')) return p;
        return `<p class="essay-paragraph">${p.replace(/\n/g, '<br>')}</p>`;
    }).filter(Boolean);
    
    return blocks.join('\n');
}

class PapersJournal {
    constructor() {
        this.papers = [];
        this.filteredPapers = [];
        this.currentTheme = localStorage.getItem('theme') || 'light';
        
        // Reading State Engine
        this.userId = localStorage.getItem('dr_paper_user_id') || 'default';
        this.activeTab = localStorage.getItem('dr_paper_active_tab') || 'unread';
        this.interactions = this.loadLocalInteractions();
        this.lastAction = null;
        this.toastTimer = null;
        
        this.searchTerm = '';
        this.selectedTopic = 'all';

        this.init();
    }
    
    init() {
        this.setupTheme();
        this.setupEventListeners();
        this.setupQueueTabs();
        this.loadDispatches();
        this.syncRemoteInteractions();
    }
    
    loadLocalInteractions() {
        try {
            const raw = localStorage.getItem('dr_paper_interactions');
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            return {};
        }
    }
    
    saveLocalInteractions() {
        try {
            localStorage.setItem('dr_paper_interactions', JSON.stringify(this.interactions));
        } catch (e) {}
    }
    
    setupTheme() {
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            if (icon) icon.className = this.currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }
    
    setupEventListeners() {
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
        
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchTerm = e.target.value;
                this.filterDispatches();
            });
        }
        
        const topicFilter = document.getElementById('topicFilter');
        if (topicFilter) {
            topicFilter.addEventListener('change', (e) => {
                this.selectedTopic = e.target.value;
                this.filterDispatches();
            });
        }

        // Empty state buttons
        const viewArchiveBtn = document.getElementById('viewArchiveBtn');
        if (viewArchiveBtn) {
            viewArchiveBtn.addEventListener('click', () => this.switchTab('all'));
        }

        const viewSavedBtn = document.getElementById('viewSavedBtn');
        if (viewSavedBtn) {
            viewSavedBtn.addEventListener('click', () => this.switchTab('saved'));
        }

        // Handle URL hash changes (#arxiv_id)
        window.addEventListener('hashchange', () => this.handleDeepLink());
    }

    setupQueueTabs() {
        const tabs = document.querySelectorAll('.feed-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTab = tab.getAttribute('data-tab');
                this.switchTab(targetTab);
            });
        });
        this.updateTabUI();
    }

    switchTab(tabName) {
        if (!['unread', 'saved', 'all'].includes(tabName)) return;
        this.activeTab = tabName;
        localStorage.setItem('dr_paper_active_tab', tabName);
        this.updateTabUI();
        this.filterDispatches();
    }

    updateTabUI() {
        const tabs = document.querySelectorAll('.feed-tab');
        tabs.forEach(tab => {
            const isTarget = tab.getAttribute('data-tab') === this.activeTab;
            tab.classList.toggle('active', isTarget);
            tab.setAttribute('aria-selected', isTarget ? 'true' : 'false');
        });
    }

    updateTabCounts() {
        let unreadCount = 0;
        let savedCount = 0;
        const allCount = this.papers.length;

        this.papers.forEach(p => {
            const aid = p.arxiv_id;
            const inter = this.interactions[aid] || {};
            if (!inter.is_read) unreadCount++;
            if (inter.is_bookmarked) savedCount++;
        });

        const unreadElem = document.getElementById('countUnread');
        const savedElem = document.getElementById('countSaved');
        const allElem = document.getElementById('countAll');
        const emptySavedElem = document.getElementById('savedEmptyCount');

        if (unreadElem) unreadElem.textContent = unreadCount;
        if (savedElem) savedElem.textContent = savedCount;
        if (allElem) allElem.textContent = allCount;
        if (emptySavedElem) emptySavedElem.textContent = savedCount;
    }
    
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        localStorage.setItem('theme', this.currentTheme);
        
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            if (icon) icon.className = this.currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }
    
    async loadDispatches() {
        try {
            this.papers = await this.fetchDispatches();
            
            // Prioritize featured papers first, then sort by date descending
            this.papers.sort((a, b) => {
                if (a.is_featured && !b.is_featured) return -1;
                if (!a.is_featured && b.is_featured) return 1;
                return new Date(b.published_at || b.created_at) - new Date(a.published_at || a.created_at);
            });
            
            this.updateStats();
            this.updateTabCounts();
            this.populateTopicFilter();
            this.filterDispatches();
            this.hideLoading();
            this.handleDeepLink();
            
        } catch (error) {
            console.error('Error loading papers:', error);
            this.showError(error.message);
        }
    }

    async syncRemoteInteractions() {
        if (!SUPABASE_CONFIG.url || !SUPABASE_CONFIG.anonKey) return;
        try {
            const endpoint = `${SUPABASE_CONFIG.url.replace(/\/$/, '')}/rest/v1/user_interactions?user_id=eq.${encodeURIComponent(this.userId)}&select=*`;
            const response = await fetch(endpoint, {
                headers: {
                    'apikey': SUPABASE_CONFIG.anonKey,
                    'Authorization': `Bearer ${SUPABASE_CONFIG.anonKey}`,
                    'Accept-Profile': SUPABASE_CONFIG.schema
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (Array.isArray(data) && data.length > 0) {
                    data.forEach(row => {
                        this.interactions[row.arxiv_id] = {
                            is_read: Boolean(row.is_read),
                            is_bookmarked: Boolean(row.is_bookmarked),
                            is_starred: Boolean(row.is_starred),
                            read_at: row.read_at
                        };
                    });
                    this.saveLocalInteractions();
                    this.updateTabCounts();
                    this.filterDispatches();
                }
            }
        } catch (err) {
            console.warn('[Dr. Paper] Cross-device sync notice:', err);
        }
    }

    async persistInteraction(arxivId) {
        this.saveLocalInteractions();
        this.updateTabCounts();
        
        if (!SUPABASE_CONFIG.url || !SUPABASE_CONFIG.anonKey) return;
        try {
            const data = this.interactions[arxivId] || {};
            const endpoint = `${SUPABASE_CONFIG.url.replace(/\/$/, '')}/rest/v1/user_interactions`;
            await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'apikey': SUPABASE_CONFIG.anonKey,
                    'Authorization': `Bearer ${SUPABASE_CONFIG.anonKey}`,
                    'Content-Type': 'application/json',
                    'Content-Profile': SUPABASE_CONFIG.schema,
                    'Prefer': 'resolution=merge-duplicates'
                },
                body: JSON.stringify({
                    user_id: this.userId,
                    arxiv_id: arxivId,
                    is_read: Boolean(data.is_read),
                    is_bookmarked: Boolean(data.is_bookmarked),
                    is_starred: Boolean(data.is_starred),
                    read_at: data.read_at || (data.is_read ? new Date().toISOString() : null),
                    updated_at: new Date().toISOString()
                })
            });
        } catch (err) {
            console.warn('[Dr. Paper] PostgREST interaction write error:', err);
        }
    }
    
    async fetchDispatches() {
        // 1. Query Supabase PostgREST for published papers
        if (SUPABASE_CONFIG.url && SUPABASE_CONFIG.anonKey) {
            try {
                const endpoint = `${SUPABASE_CONFIG.url.replace(/\/$/, '')}/rest/v1/papers?status=eq.published&select=*&order=published_at.desc&limit=50`;
                const response = await fetch(endpoint, {
                    headers: {
                        'apikey': SUPABASE_CONFIG.anonKey,
                        'Authorization': `Bearer ${SUPABASE_CONFIG.anonKey}`,
                        'Accept-Profile': SUPABASE_CONFIG.schema
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (Array.isArray(data) && data.length > 0) {
                        return data;
                    }
                }
            } catch (err) {
                console.warn('[Dr. Paper] Supabase query failed, falling back:', err);
            }
        }
        
        // 2. Demo dataset fallback
        return this.getDemoDispatches();
    }
    
    getDemoDispatches() {
        return [
            {
                arxiv_id: '2609.03153',
                title: 'VeriPhy: Agentic Physical Reasoning for World Model Evaluation and Refinement',
                authors: ['World Model Lab'],
                topic: 'Robotics & Physical AI',
                score: 14.5,
                is_featured: true,
                curated_source: 'Hugging Face Daily',
                published_edition: '2026-W36',
                editorial_notes: 'Physical reasoning has always been a major blind spot for generative world models. VeriPhy introduces deterministic verification steps.',
                published_at: '2026-09-06T00:00:00Z',
                pdf_url: 'https://arxiv.org/pdf/2609.03153.pdf',
                hf_url: 'https://huggingface.co/papers/2609.03153',
                summary: 'Evaluating world models requires validating physical consistency. VeriPhy provides an agentic evaluation framework with deterministic verification.',
                structured_analysis: {
                    one_line_hook: 'VeriPhy introduces deterministic verification steps to eliminate physics hallucinations in multimodal world models.',
                    plain_english_gist: 'VeriPhy provides an automated verification tool that checks if video and multimodal AI models obey fundamental physical laws (gravity, collision, momentum) instead of hallucinating impossible physics.',
                    essay_markdown: `### The Motivation
Generative world models frequently generate plausible-looking videos that violate basic Newtonian physics. VeriPhy formalizes physical verification by decomposing actions into verifiable state transitions.

### How it Works
The system uses automated agentic inspectors that test collision boundaries, momentum conservation, and object permanency in synthetic trajectories.

### Results & Tradeoffs
Eliminates physical hallucination by 64% in simulated robot benchmarks with minimal inference overhead.`,
                    key_takeaways: [
                        'Eliminates hallucinated physics by 64% in simulated benchmarks.',
                        'Integrates with existing vision-language models without retraining.',
                        'Provides deterministic validation for autonomous agent world models.'
                    ]
                }
            }
        ];
    }
    
    updateStats() {
        const totalPapersEl = document.getElementById('totalPapers');
        const totalTopicsEl = document.getElementById('totalTopics');
        const lastUpdatedEl = document.getElementById('lastUpdated');
        
        if (totalPapersEl) totalPapersEl.textContent = this.papers.length;
        
        if (totalTopicsEl) {
            const topics = new Set(this.papers.map(p => p.topic).filter(Boolean));
            totalTopicsEl.textContent = topics.size;
        }
        
        if (lastUpdatedEl && this.papers.length > 0) {
            const latest = this.papers[0].published_edition || '2026-W36';
            lastUpdatedEl.textContent = latest;
        }
    }
    
    populateTopicFilter() {
        const topicFilter = document.getElementById('topicFilter');
        if (!topicFilter) return;
        
        const topics = [...new Set(this.papers.map(p => p.topic).filter(Boolean))].sort();
        
        while (topicFilter.options.length > 1) {
            topicFilter.remove(1);
        }
        
        topics.forEach(topic => {
            const option = document.createElement('option');
            option.value = topic;
            option.textContent = topic;
            topicFilter.appendChild(option);
        });
    }
    
    filterDispatches() {
        const search = (this.searchTerm || '').toLowerCase().trim();
        const topic = this.selectedTopic || 'all';
        
        this.filteredPapers = this.papers.filter(paper => {
            const aid = paper.arxiv_id;
            const inter = this.interactions[aid] || {};
            
            // Queue Tab Filtering
            if (this.activeTab === 'unread') {
                if (inter.is_read) return false;
            } else if (this.activeTab === 'saved') {
                if (!inter.is_bookmarked) return false;
            }
            // 'all' includes everything
            
            // Topic Filter
            const matchesTopic = topic === 'all' || paper.topic === topic;
            if (!matchesTopic) return false;
            
            // Search Query Filter
            if (!search) return true;
            
            const title = (paper.title || '').toLowerCase();
            const summary = (paper.summary || '').toLowerCase();
            const authors = (Array.isArray(paper.authors) ? paper.authors.join(' ') : '').toLowerCase();
            const notes = (paper.editorial_notes || '').toLowerCase();
            const gist = (paper.structured_analysis?.plain_english_gist || '').toLowerCase();
            const essay = (paper.structured_analysis?.essay_markdown || '').toLowerCase();
            const arxiv = (paper.arxiv_id || '').toLowerCase();
            
            return title.includes(search) ||
                   summary.includes(search) ||
                   authors.includes(search) ||
                   notes.includes(search) ||
                   gist.includes(search) ||
                   essay.includes(search) ||
                   arxiv.includes(search);
        });
        
        this.renderDispatches();
    }
    
    renderDispatches() {
        const grid = document.getElementById('papersGrid');
        const noResults = document.getElementById('noResults');
        const allCaughtUp = document.getElementById('allCaughtUp');
        if (!grid) return;
        
        if (this.filteredPapers.length === 0) {
            grid.style.display = 'none';
            if (this.activeTab === 'unread' && !this.searchTerm && this.selectedTopic === 'all') {
                if (allCaughtUp) allCaughtUp.style.display = 'block';
                if (noResults) noResults.style.display = 'none';
            } else {
                if (allCaughtUp) allCaughtUp.style.display = 'none';
                if (noResults) noResults.style.display = 'block';
            }
            return;
        }
        
        grid.style.display = 'flex';
        if (noResults) noResults.style.display = 'none';
        if (allCaughtUp) allCaughtUp.style.display = 'none';
        grid.innerHTML = '';
        
        this.filteredPapers.forEach(paper => {
            const article = this.createDispatchArticle(paper);
            grid.appendChild(article);
        });
    }
    
    createDispatchArticle(paper) {
        const template = document.getElementById('paperCardTemplate');
        const node = template.content.cloneNode(true);
        const article = node.querySelector('article');
        const arxivId = paper.arxiv_id;
        const inter = this.interactions[arxivId] || {};

        article.setAttribute('data-arxiv-id', arxivId || '');
        if (arxivId) article.id = `paper-${arxivId.replace(/[^a-zA-Z0-9]/g, '_')}`;
        
        // Metadata line
        const dateStr = paper.published_at || paper.created_at;
        const formattedDate = dateStr ? new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
        
        article.querySelector('.article-edition').textContent = paper.published_edition || 'Issue';
        article.querySelector('.article-date').textContent = formattedDate;
        article.querySelector('.article-topic').textContent = paper.topic || 'General AI';
        
        if (paper.is_featured) {
            const featuredTag = article.querySelector('.featured-tag');
            if (featuredTag) featuredTag.style.display = 'inline-flex';
        }

        const readBadge = article.querySelector('.read-badge');
        if (readBadge && inter.is_read && this.activeTab === 'all') {
            readBadge.style.display = 'inline-flex';
        }
        
        // Headline & Authors
        article.querySelector('.article-headline').textContent = paper.title || 'Untitled Paper';
        const authors = Array.isArray(paper.authors) ? paper.authors : [];
        article.querySelector('.article-authors').textContent = authors.length > 0
            ? 'By ' + authors.slice(0, 6).join(', ') + (authors.length > 6 ? ' et al.' : '')
            : '';
        
        // Curator's Note
        if (paper.editorial_notes) {
            const curatorBlock = article.querySelector('.curator-take');
            const curatorText = article.querySelector('.curator-text');
            if (curatorBlock && curatorText) {
                curatorText.textContent = paper.editorial_notes;
                curatorBlock.style.display = 'block';
            }
        }
        
        // Structured Essay Content
        const analysis = paper.structured_analysis || {};
        
        // Thesis Hook
        const hook = analysis.one_line_hook || '';
        const hookElem = article.querySelector('.thesis-hook');
        if (hookElem && hook && !analysis.essay_markdown?.includes(hook)) {
            hookElem.textContent = `“${hook}”`;
            hookElem.style.display = 'block';
        } else if (hookElem) {
            hookElem.style.display = 'none';
        }
        
        // Plain-English Gist
        const gistElem = article.querySelector('.plain-gist-card');
        const gistContent = article.querySelector('.plain-gist-content');
        const gistText = analysis.plain_english_gist || '';
        
        if (gistElem && gistContent && gistText) {
            gistContent.textContent = gistText;
            gistElem.style.display = 'block';
        } else if (gistElem) {
            gistElem.style.display = 'none';
        }
        
        // Key Takeaways Section
        const takeaways = Array.isArray(analysis.key_takeaways) ? analysis.key_takeaways : [];
        const takeawaysContainer = article.querySelector('.takeaways-container');
        const takeawaysList = article.querySelector('.takeaways-pills');
        
        if (takeaways.length > 0 && takeawaysContainer && takeawaysList) {
            takeawaysList.innerHTML = takeaways.map(t => `<li>${t}</li>`).join('');
            takeawaysContainer.style.display = 'block';
        } else if (takeawaysContainer) {
            takeawaysContainer.style.display = 'none';
        }

        // Deep Dive Expandable Section
        const deepDiveToggleBtn = article.querySelector('.deep-dive-toggle-btn');
        const deepDiveContent = article.querySelector('.deep-dive-content');
        const toggleLabel = article.querySelector('.toggle-label');

        if (deepDiveToggleBtn && deepDiveContent) {
            deepDiveToggleBtn.addEventListener('click', () => {
                const isHidden = deepDiveContent.style.display === 'none';
                deepDiveContent.style.display = isHidden ? 'block' : 'none';
                deepDiveToggleBtn.classList.toggle('expanded', isHidden);
                if (toggleLabel) {
                    toggleLabel.textContent = isHidden ? 'Hide Technical Deep Dive' : 'Read Technical Deep Dive';
                }
            });
        }

        // Essay Body inside Deep Dive
        const essayBody = article.querySelector('.essay-body');
        if (essayBody) {
            if (analysis.essay_markdown) {
                essayBody.innerHTML = renderMarkdownToHtml(analysis.essay_markdown);
            } else {
                let assembledMd = '';
                if (analysis.context_and_motivation || analysis.problem) {
                    assembledMd += `${analysis.context_and_motivation || analysis.problem}\n\n`;
                }
                if (analysis.core_mechanism || analysis.innovation) {
                    assembledMd += `### How it works\n\n${analysis.core_mechanism || analysis.innovation}\n\n`;
                }
                if (analysis.empirical_results || analysis.impact) {
                    assembledMd += `### Evaluation\n\n${analysis.empirical_results || analysis.impact}\n\n`;
                }
                if (analysis.critique_and_tradeoffs) {
                    assembledMd += `### Limitations & Trade-offs\n\n${analysis.critique_and_tradeoffs}\n\n`;
                }
                essayBody.innerHTML = renderMarkdownToHtml(assembledMd);
            }
        }
        
        // Abstract Drawer
        const abstractBtn = article.querySelector('.toggle-abstract-btn');
        const abstractContent = article.querySelector('.abstract-content');
        if (abstractBtn && abstractContent) {
            abstractContent.textContent = paper.summary || 'No abstract text available.';
            abstractBtn.addEventListener('click', () => {
                const isHidden = abstractContent.style.display === 'none';
                abstractContent.style.display = isHidden ? 'block' : 'none';
                abstractBtn.classList.toggle('expanded', isHidden);
            });
        }
        
        // Links
        const arxivBtn = article.querySelector('.arxiv-link');
        const pdfBtn = article.querySelector('.pdf-link');
        const hfBtn = article.querySelector('.hf-link');
        const shareBtn = article.querySelector('.share-icon-btn');
        
        if (arxivId && arxivBtn) {
            arxivBtn.href = `https://arxiv.org/abs/${arxivId}`;
        } else if (arxivBtn) {
            arxivBtn.style.display = 'none';
        }
        
        if (paper.pdf_url && pdfBtn) {
            pdfBtn.href = paper.pdf_url;
        } else if (arxivId && pdfBtn) {
            pdfBtn.href = `https://arxiv.org/pdf/${arxivId}.pdf`;
        } else if (pdfBtn) {
            pdfBtn.style.display = 'none';
        }
        
        if ((paper.hf_url || arxivId) && hfBtn) {
            hfBtn.href = paper.hf_url || `https://huggingface.co/papers/${arxivId}`;
            hfBtn.style.display = 'inline-flex';
        }
        
        if (shareBtn) {
            shareBtn.addEventListener('click', () => this.sharePaper(paper));
        }

        // ==============================================================================
        // Card Action Toolbar (Bookmark, Star, Mark as Read / Dismiss)
        // ==============================================================================
        const bookmarkBtn = article.querySelector('.btn-bookmark');
        const starBtn = article.querySelector('.btn-star');
        const dismissBtn = article.querySelector('.btn-dismiss');

        if (bookmarkBtn) {
            if (inter.is_bookmarked) {
                bookmarkBtn.classList.add('active');
                bookmarkBtn.querySelector('i').className = 'fas fa-bookmark';
            }
            bookmarkBtn.addEventListener('click', () => this.toggleBookmark(paper, bookmarkBtn, article));
        }

        if (starBtn) {
            if (inter.is_starred) {
                starBtn.classList.add('active');
                starBtn.querySelector('i').className = 'fas fa-star';
            }
            starBtn.addEventListener('click', () => this.toggleStar(paper, starBtn));
        }

        if (dismissBtn) {
            if (inter.is_read) {
                dismissBtn.classList.add('is-read');
                dismissBtn.querySelector('.action-text').textContent = 'Read';
            }
            dismissBtn.addEventListener('click', () => this.toggleRead(paper, article));
        }

        // Touch Swipe to Dismiss on mobile
        this.setupCardSwipeGesture(article, paper);
        
        return article;
    }

    setupCardSwipeGesture(articleElem, paper) {
        let touchStartX = 0;
        let touchStartY = 0;
        let touchCurrentX = 0;
        let isSwiping = false;

        articleElem.addEventListener('touchstart', (e) => {
            if (e.touches.length !== 1) return;
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            isSwiping = false;
        }, { passive: true });

        articleElem.addEventListener('touchmove', (e) => {
            if (e.touches.length !== 1) return;
            touchCurrentX = e.touches[0].clientX;
            const diffX = touchCurrentX - touchStartX;
            const diffY = e.touches[0].clientY - touchStartY;

            // Detect horizontal swipe vs vertical scroll
            if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 20) {
                if (diffX < 0) { // Swipe left
                    isSwiping = true;
                    articleElem.style.transform = `translateX(${diffX * 0.7}px)`;
                    articleElem.style.opacity = `${Math.max(0.3, 1 - Math.abs(diffX) / 300)}`;
                }
            }
        }, { passive: true });

        articleElem.addEventListener('touchend', () => {
            if (!isSwiping) return;
            const diffX = touchCurrentX - touchStartX;
            
            if (diffX < -100) { // Threshold reached
                this.toggleRead(paper, articleElem);
            } else {
                // Reset position
                articleElem.style.transform = '';
                articleElem.style.opacity = '';
            }
            isSwiping = false;
        }, { passive: true });
    }

    toggleRead(paper, articleElem) {
        const aid = paper.arxiv_id;
        if (!this.interactions[aid]) this.interactions[aid] = {};
        
        const currentState = Boolean(this.interactions[aid].is_read);
        const newState = !currentState;
        this.interactions[aid].is_read = newState;
        this.interactions[aid].read_at = newState ? new Date().toISOString() : null;

        // Record for undo
        this.lastAction = { type: 'read', arxivId: aid, previousState: currentState, title: paper.title };

        if (this.activeTab === 'unread' && newState) {
            // Animate card slide-away
            if (articleElem) {
                articleElem.classList.add('dismissing');
                setTimeout(() => {
                    this.filterDispatches();
                }, 260);
            } else {
                this.filterDispatches();
            }
            this.showToast(`Marked "${(paper.title || 'Paper').slice(0, 36)}..." as read.`, true);
        } else {
            this.filterDispatches();
            this.showToast(newState ? 'Marked as read.' : 'Marked as unread.');
        }

        this.persistInteraction(aid);
    }

    toggleBookmark(paper, btnElem, articleElem) {
        const aid = paper.arxiv_id;
        if (!this.interactions[aid]) this.interactions[aid] = {};
        
        const newState = !this.interactions[aid].is_bookmarked;
        this.interactions[aid].is_bookmarked = newState;

        if (btnElem) {
            btnElem.classList.toggle('active', newState);
            const icon = btnElem.querySelector('i');
            if (icon) icon.className = newState ? 'fas fa-bookmark' : 'far fa-bookmark';
        }

        if (this.activeTab === 'saved' && !newState && articleElem) {
            articleElem.classList.add('dismissing');
            setTimeout(() => this.filterDispatches(), 260);
        }

        this.showToast(newState ? 'Saved to Bookmarks.' : 'Removed from Bookmarks.');
        this.persistInteraction(aid);
    }

    toggleStar(paper, btnElem) {
        const aid = paper.arxiv_id;
        if (!this.interactions[aid]) this.interactions[aid] = {};
        
        const newState = !this.interactions[aid].is_starred;
        this.interactions[aid].is_starred = newState;

        if (btnElem) {
            btnElem.classList.toggle('active', newState);
            const icon = btnElem.querySelector('i');
            if (icon) icon.className = newState ? 'fas fa-star' : 'far fa-star';
        }

        this.showToast(newState ? 'Starred paper.' : 'Removed star.');
        this.persistInteraction(aid);
    }

    undoLastAction() {
        if (!this.lastAction) return;
        const { type, arxivId, previousState } = this.lastAction;
        
        if (type === 'read') {
            if (!this.interactions[arxivId]) this.interactions[arxivId] = {};
            this.interactions[arxivId].is_read = previousState;
            this.persistInteraction(arxivId);
            this.filterDispatches();
            this.showToast('Action undone.');
        }
        this.lastAction = null;
    }
    
    sharePaper(paper) {
        const title = paper.title || 'Research Paper';
        const url = paper.arxiv_id ? `${window.location.origin}${window.location.pathname}#${paper.arxiv_id}` : window.location.href;
        const text = `Read "${title}" on Dr. Paper:`;
        
        if (navigator.share) {
            navigator.share({ title, text, url }).catch(() => {});
        } else {
            navigator.clipboard.writeText(`${text} ${url}`).then(() => {
                this.showToast('Paper link copied to clipboard.');
            });
        }
    }

    handleDeepLink() {
        const hash = window.location.hash.replace('#', '').trim();
        if (!hash) return;

        // If target paper is in database, switch to 'all' tab if needed so it's visible
        const target = this.papers.find(p => p.arxiv_id === hash);
        if (target) {
            const inter = this.interactions[target.arxiv_id] || {};
            if (inter.is_read && this.activeTab === 'unread') {
                this.switchTab('all');
            }

            setTimeout(() => {
                const elemId = `paper-${hash.replace(/[^a-zA-Z0-9]/g, '_')}`;
                const elem = document.getElementById(elemId);
                if (elem) {
                    elem.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    elem.style.outline = '2px solid var(--accent-amber)';
                    setTimeout(() => { elem.style.outline = ''; }, 2500);
                }
            }, 350);
        }
    }
    
    showToast(message, canUndo = false) {
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();
        if (this.toastTimer) clearTimeout(this.toastTimer);

        const toast = document.createElement('div');
        toast.className = 'toast';
        
        const msgSpan = document.createElement('span');
        msgSpan.textContent = message;
        toast.appendChild(msgSpan);

        if (canUndo) {
            const undoBtn = document.createElement('button');
            undoBtn.className = 'toast-undo-btn';
            undoBtn.textContent = 'Undo';
            undoBtn.addEventListener('click', () => {
                this.undoLastAction();
                toast.remove();
            });
            toast.appendChild(undoBtn);
        }
        
        document.body.appendChild(toast);
        
        this.toastTimer = setTimeout(() => {
            if (toast && toast.parentNode) {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.2s ease';
                setTimeout(() => toast.remove(), 200);
            }
        }, canUndo ? 4500 : 3000);
    }
    
    hideLoading() {
        const spinner = document.getElementById('loadingSpinner');
        if (spinner) spinner.style.display = 'none';
    }
    
    showError(msg) {
        this.hideLoading();
        const err = document.getElementById('errorMessage');
        const errText = document.getElementById('errorText');
        if (err) err.style.display = 'block';
        if (errText && msg) errText.textContent = `Error loading papers: ${msg}`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.journalApp = new PapersJournal();
});