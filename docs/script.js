// ==============================================================================
// Dr. Paper: Frontend Web Client (The Morning Paper Research Journal)
// Live PostgREST integration with Supabase (status='published')
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
        this.init();
    }
    
    init() {
        this.setupTheme();
        this.setupEventListeners();
        this.loadDispatches();
    }
    
    setupTheme() {
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            icon.className = this.currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
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
                const topicFilter = document.getElementById('topicFilter');
                this.filterDispatches(e.target.value, topicFilter ? topicFilter.value : 'all');
            });
        }
        
        const topicFilter = document.getElementById('topicFilter');
        if (topicFilter) {
            topicFilter.addEventListener('change', (e) => {
                const searchInput = document.getElementById('searchInput');
                this.filterDispatches(searchInput ? searchInput.value : '', e.target.value);
            });
        }
    }
    
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        localStorage.setItem('theme', this.currentTheme);
        
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            icon.className = this.currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }
    
    async loadDispatches() {
        try {
            this.papers = await this.fetchDispatches();
            
            // Prioritize featured papers first, then sort by published date descending
            this.papers.sort((a, b) => {
                if (a.is_featured && !b.is_featured) return -1;
                if (!a.is_featured && b.is_featured) return 1;
                return new Date(b.published_at || b.created_at) - new Date(a.published_at || a.created_at);
            });
            
            this.filteredPapers = [...this.papers];
            
            this.updateStats();
            this.populateTopicFilter();
            this.renderDispatches();
            this.hideLoading();
            
        } catch (error) {
            console.error('Error loading dispatches:', error);
            this.showError(error.message);
        }
    }
    
    async fetchDispatches() {
        // 1. Query Supabase PostgREST for published dispatches
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
                        console.log(`[Dr. Paper] Loaded ${data.length} published dispatches from Supabase (${SUPABASE_CONFIG.schema})`);
                        return data;
                    }
                }
            } catch (err) {
                console.warn('[Dr. Paper] Supabase query failed, falling back to local snapshot:', err);
            }
        }
        
        // 2. Fallback to static papers.json
        try {
            const response = await fetch('papers.json');
            if (response.ok) {
                const data = await response.json();
                const publishedList = (data.papers || []).filter(p => !p.status || p.status === 'published');
                return publishedList.length > 0 ? publishedList : data.papers;
            }
        } catch (err) {
            console.warn('[Dr. Paper] Local fallback load failed:', err);
        }
        
        // 3. Demo dataset
        return this.getDemoDispatches();
    }
    
    getDemoDispatches() {
        return [
            {
                arxiv_id: '2407.08608',
                title: 'FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-Precision',
                authors: ['Tri Dao', 'Jay Shah'],
                topic: 'Systems & Efficiency',
                score: 9.8,
                is_featured: true,
                curated_source: 'huggingface',
                published_edition: '2026-W36',
                editorial_notes: 'Tri Dao does it again. Overlapping TMA transfers with WGMMA compute is a masterclass in GPU hardware exploitation.',
                published_at: '2026-09-05T00:00:00Z',
                pdf_url: 'https://arxiv.org/pdf/2407.08608.pdf',
                hf_url: 'https://huggingface.co/papers/2407.08608',
                summary: 'Attention is the core computational bottleneck in scaling Transformers. FlashAttention-3 introduces warp-specialization, hardware asynchrony on NVIDIA Hopper H100 GPUs, and block-quantized FP8 execution.',
                structured_analysis: {
                    one_line_hook: 'FlashAttention-3 overlaps TMA memory transfers with WGMMA tensor compute, extracting ~75% of theoretical H100 peak throughput without sacrificing FP8 accuracy.',
                    essay_markdown: `### The Tension in Existing Systems
Attention still dominates the FLOP budget and execution latency of large Transformers. While FlashAttention-2 made massive strides by optimizing IO access patterns on Ampere GPUs, it left a substantial fraction of NVIDIA's Hopper architecture idle. Specifically, Hopper introduced dedicated hardware units—the Tensor Memory Accelerator (TMA) and Warp-Group Matrix Multiply-Accumulate (WGMMA)—that standard kernels leave underutilized due to sequential dependencies between DRAM loads, matrix multiplications, and softmax reductions.

### The Architectural Trick: Warp-Specialization & Asynchrony
The core insight of FlashAttention-3 is to decouple data movement from compute using hardware-level warp-specialization. Rather than having all threads simultaneously fetch and compute, the kernel partitions warps into dedicated *producers* (which issue asynchronous TMA transfers into a shared circular buffer) and *consumers* (which feed WGMMA tensor instructions in parallel). A single warp-level barrier per tile coordinates the pipeline without global synchronization.

To push throughput further without numeric instability, the authors implement dynamic per-tile FP8 quantization. Each 64-element block of Q and K is scaled dynamically during the online softmax pass, keeping intermediate accumulations in FP16 before final downcasting.

### The Empirical Reality Check
Benchmarked on NVIDIA H100 SXM GPUs, FlashAttention-3 reaches 740 TFLOPs/s in FP16—representing ~75% of theoretical hardware capacity. In FP8, throughput exceeds 1.2 PFLOPs/s. Across end-to-end language modeling workloads, this translates to a 1.5x speedup on 70B decoders (12.4ms vs 18.6ms per token) and a 2.0x speedup on 13B encoders, with zero measurable perplexity degradation on WikiText-103 and GSM8K.

### Where the Catch Lies
The primary limitation is portability: these optimizations depend strictly on Hopper-specific SM90a instructions. On older Ampere or Volta GPUs, or non-NVIDIA accelerators like AMD's MI300, the kernel falls back to standard FlashAttention-2 speeds. Additionally, the producer-consumer circular buffer assumes sequence lengths can fill the pipeline without memory stalls; workloads with heavy KV-cache fragmentation may see lower utilization.`,
                    key_takeaways: [
                        'Lifts H100 FP16 attention utilization to 75% of theoretical peak (740 TFLOPs/s).',
                        'Eliminates memory stalls via asynchronous producer-consumer warp specialization.',
                        'Preserves baseline perplexity using per-tile FP8 block quantization.'
                    ]
                }
            },
            {
                arxiv_id: '1706.03762',
                title: 'Attention Is All You Need',
                authors: ['Ashish Vaswani', 'Noam Shazeer', 'Niki Parmar', 'Jakob Uszkoreit'],
                topic: 'Foundation Models',
                score: 9.9,
                is_featured: false,
                curated_source: 'arxiv',
                published_edition: '2026-W36',
                editorial_notes: 'The seminal paper that introduced multi-head self-attention and launched the modern transformer era.',
                published_at: '2026-09-01T00:00:00Z',
                pdf_url: 'https://arxiv.org/pdf/1706.03762.pdf',
                hf_url: 'https://huggingface.co/papers/1706.03762',
                summary: 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.',
                structured_analysis: {
                    one_line_hook: 'Replacing recurrence entirely with multi-head self-attention reduces path length to O(1) and unlocks massive training parallelism.',
                    essay_markdown: `### The Bottleneck of Sequential Recurrence
Prior to this work, state-of-the-art sequence transduction relied almost exclusively on recurrent neural networks (RNNs, LSTMs, and GRUs). While conceptually elegant, sequential recurrence imposes a fundamental computational barrier: because hidden state $h_t$ strictly depends on $h_{t-1}$, training cannot be parallelized across the time dimension. On long sequence lengths, this constraint severely bottlenecks GPU utilization.

### Multi-Head Attention as a Drop-in Architecture
The Transformer replaces recurrence entirely with Multi-Head Self-Attention (MHA) and sinusoidal positional encodings. Rather than compressing context into a single recurrent vector, every token computes attention weights across all other positions simultaneously. By projecting queries, keys, and values into multiple representation subspaces, the model learns diverse linguistic dependencies (syntax, semantics, coreference) in parallel matrix multiplications.

### Empirical Validation
On the WMT 2014 English-to-German translation benchmark, the Transformer established a new state of the art at 28.4 BLEU (outperforming existing ensembles by over 2.0 BLEU points), while requiring only 3.5 days of training on 8 P100 GPUs—a fraction of the compute cost of prior recurrent baselines.

### Architectural Trade-offs
While parallel training throughput is unlocked, the trade-off is memory complexity: standard self-attention exhibits $O(N^2)$ memory and computational cost in sequence length $N$, creating an engineering challenge for ultra-long context windows that subsequent researchers would spend years trying to resolve.`,
                    key_takeaways: [
                        'O(1) sequential path length across all tokens vs O(N) in recurrent models.',
                        'Multi-Head Attention enables attending across distinct representation subspaces in parallel.',
                        'Unlocks massive GPU training parallelization at the cost of O(N^2) quadratic context memory.'
                    ]
                }
            }
        ];
    }
    
    updateStats() {
        const topics = [...new Set(this.papers.map(p => p.topic).filter(Boolean))];
        const latestDate = this.papers.length > 0 && this.papers[0].published_at
            ? new Date(this.papers[0].published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
            : 'Recent';
        
        const totalElem = document.getElementById('totalPapers');
        const topicsElem = document.getElementById('totalTopics');
        const updatedElem = document.getElementById('lastUpdated');
        
        if (totalElem) totalElem.textContent = this.papers.length;
        if (topicsElem) topicsElem.textContent = topics.length;
        if (updatedElem) updatedElem.textContent = latestDate;
    }
    
    populateTopicFilter() {
        const topics = [...new Set(this.papers.map(p => p.topic).filter(Boolean))].sort();
        const topicFilter = document.getElementById('topicFilter');
        if (!topicFilter) return;
        
        topicFilter.innerHTML = '<option value="all">All Disciplines</option>';
        topics.forEach(topic => {
            const option = document.createElement('option');
            option.value = topic;
            option.textContent = topic;
            topicFilter.appendChild(option);
        });
    }
    
    filterDispatches(searchTerm = '', selectedTopic = 'all') {
        const query = searchTerm.toLowerCase().trim();
        
        this.filteredPapers = this.papers.filter(paper => {
            const title = (paper.title || '').toLowerCase();
            const authors = Array.isArray(paper.authors) ? paper.authors.join(' ').toLowerCase() : '';
            const summary = (paper.summary || '').toLowerCase();
            const topic = (paper.topic || '').toLowerCase();
            const analysis = paper.structured_analysis ? JSON.stringify(paper.structured_analysis).toLowerCase() : '';
            const notes = (paper.editorial_notes || '').toLowerCase();
            
            const matchesSearch = !query || 
                title.includes(query) ||
                authors.includes(query) ||
                summary.includes(query) ||
                topic.includes(query) ||
                analysis.includes(query) ||
                notes.includes(query);
            
            const matchesTopic = selectedTopic === 'all' || paper.topic === selectedTopic;
            return matchesSearch && matchesTopic;
        });
        
        this.renderDispatches();
    }
    
    renderDispatches() {
        const grid = document.getElementById('papersGrid');
        const noResults = document.getElementById('noResults');
        if (!grid) return;
        
        if (this.filteredPapers.length === 0) {
            grid.style.display = 'none';
            if (noResults) noResults.style.display = 'block';
            return;
        }
        
        grid.style.display = 'flex';
        if (noResults) noResults.style.display = 'none';
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
        
        // Headline & Authors
        article.querySelector('.article-headline').textContent = paper.title || 'Untitled Dispatch';
        const authors = Array.isArray(paper.authors) ? paper.authors : [];
        article.querySelector('.article-authors').textContent = authors.length > 0
            ? 'By ' + authors.slice(0, 6).join(', ') + (authors.length > 6 ? ' et al.' : '')
            : '';
        
        // Curator's Note (Human Editorial Lead)
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
        
        // Thesis Hook (only show if unique from essay content)
        const hook = analysis.one_line_hook || '';
        const hookElem = article.querySelector('.thesis-hook');
        if (hookElem && hook && !analysis.essay_markdown?.includes(hook)) {
            hookElem.textContent = `“${hook}”`;
            hookElem.style.display = 'block';
        } else if (hookElem) {
            hookElem.style.display = 'none';
        }
        
        // Plain-English Gist (Executive summary for GenAI practitioners & enthusiasts)
        const gistElem = article.querySelector('.plain-gist-card');
        const gistContent = article.querySelector('.plain-gist-content');
        const gistText = analysis.plain_english_gist || '';
        
        if (gistElem && gistContent && gistText) {
            gistContent.textContent = gistText;
            gistElem.style.display = 'block';
        } else if (gistElem) {
            gistElem.style.display = 'none';
        }
        
        // Key Takeaways Section (Always visible on card)
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
                // Smoothly connect legacy structured fields into readable paragraphs without redundant headers
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
        const arxivId = paper.arxiv_id;
        
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
        
        return article;
    }
    
    sharePaper(paper) {
        const title = paper.title || 'Research Paper';
        const url = paper.arxiv_id ? `https://arxiv.org/abs/${paper.arxiv_id}` : window.location.href;
        const text = `Read "${title}" on Dr. Paper:`;
        
        if (navigator.share) {
            navigator.share({ title, text, url }).catch(() => {});
        } else {
            navigator.clipboard.writeText(`${text} ${url}`).then(() => {
                this.showToast('Paper link copied to clipboard.');
            });
        }
    }
    
    showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2800);
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
    new PapersJournal();
});