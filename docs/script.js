// Research Papers Website JavaScript
class PapersWebsite {
    constructor() {
        this.papers = [];
        this.filteredPapers = [];
        this.currentTheme = localStorage.getItem('theme') || 'light';
        
        this.init();
    }
    
    init() {
        this.setupTheme();
        this.setupEventListeners();
        this.loadPapers();
    }
    
    setupTheme() {
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        const themeToggle = document.getElementById('themeToggle');
        const icon = themeToggle.querySelector('i');
        
        if (this.currentTheme === 'dark') {
            icon.className = 'fas fa-sun';
        } else {
            icon.className = 'fas fa-moon';
        }
    }
    
    setupEventListeners() {
        // Theme toggle
        document.getElementById('themeToggle').addEventListener('click', () => {
            this.toggleTheme();
        });
        
        // Search
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.filterPapers(e.target.value, document.getElementById('topicFilter').value);
        });
        
        // Topic filter
        document.getElementById('topicFilter').addEventListener('change', (e) => {
            this.filterPapers(document.getElementById('searchInput').value, e.target.value);
        });
    }
    
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        localStorage.setItem('theme', this.currentTheme);
        
        const themeToggle = document.getElementById('themeToggle');
        const icon = themeToggle.querySelector('i');
        
        if (this.currentTheme === 'dark') {
            icon.className = 'fas fa-sun';
        } else {
            icon.className = 'fas fa-moon';
        }
    }
    
    async loadPapers() {
        try {
            // In a real implementation, this would fetch from your API
            // For now, we'll use demo data
            this.papers = await this.fetchPapers();
            
            // Sort papers by date in decreasing order (newest first)
            this.papers.sort((a, b) => new Date(b.date) - new Date(a.date));
            this.filteredPapers = [...this.papers];
            
            this.updateStats();
            this.populateTopicFilter();
            this.renderPapers();
            this.hideLoading();
            
        } catch (error) {
            console.error('Error loading papers:', error);
            this.showError();
        }
    }
    
    async fetchPapers() {
        try {
            const response = await fetch('papers.json');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            // Update metadata if available
            if (data.metadata) {
                document.getElementById('totalPapers').textContent = data.metadata.total_papers || data.papers.length;
                document.getElementById('totalTopics').textContent = data.metadata.topics ? data.metadata.topics.length : 0;
                document.getElementById('lastUpdated').textContent = data.metadata.last_updated ? 
                    new Date(data.metadata.last_updated).toLocaleDateString() : 'Unknown';
            }
            
            return data.papers || [];
        } catch (error) {
            console.warn('Failed to load papers.json, using demo data:', error);
            // Fallback to demo data if papers.json is not available
            return this.getDemoData();
        }
    }
    
    getDemoData() {
        // Demo data for development/testing
        return [
            {
                id: '1',
                title: 'Attention Is All You Need',
                authors: ['Ashish Vaswani', 'Noam Shazeer', 'Niki Parmar'],
                summary: 'This paper introduces the Transformer architecture, a novel neural network design that relies entirely on attention mechanisms. The Transformer eliminates recurrence and convolutions entirely, achieving superior performance on machine translation tasks while being more parallelizable and requiring significantly less time to train.',
                topic: 'Deep Learning',
                date: '2024-01-25',
                arxiv_id: '1706.03762',
                pdf_url: 'https://arxiv.org/pdf/1706.03762.pdf'
            },
            {
                id: '2',
                title: 'BERT: Pre-training of Deep Bidirectional Transformers',
                authors: ['Jacob Devlin', 'Ming-Wei Chang', 'Kenton Lee'],
                summary: 'BERT represents a significant advancement in language understanding by introducing bidirectional training of Transformer models. Unlike previous models that read text sequentially, BERT considers the full context of a word by looking at both left and right contexts simultaneously, leading to substantial improvements on eleven natural language processing tasks.',
                topic: 'NLP',
                date: '2024-01-20',
                arxiv_id: '1810.04805',
                pdf_url: 'https://arxiv.org/pdf/1810.04805.pdf'
            },
            {
                id: '3',
                title: 'Generative Adversarial Networks',
                authors: ['Ian Goodfellow', 'Jean Pouget-Abadie', 'Mehdi Mirza'],
                summary: 'This groundbreaking paper introduces Generative Adversarial Networks (GANs), a new framework for estimating generative models via an adversarial process. The system trains two neural networks simultaneously: a generator that creates fake data and a discriminator that attempts to distinguish real from fake data, resulting in remarkably realistic synthetic data generation.',
                topic: 'Machine Learning',
                date: '2024-01-15',
                arxiv_id: '1406.2661',
                pdf_url: 'https://arxiv.org/pdf/1406.2661.pdf'
            }
        ];
    }
    
    updateStats() {
        const topics = [...new Set(this.papers.map(paper => paper.topic))];
        const lastUpdated = new Date().toLocaleDateString();
        
        document.getElementById('totalPapers').textContent = this.papers.length;
        document.getElementById('totalTopics').textContent = topics.length;
        document.getElementById('lastUpdated').textContent = lastUpdated;
    }
    
    populateTopicFilter() {
        const topics = [...new Set(this.papers.map(paper => paper.topic))].sort();
        const topicFilter = document.getElementById('topicFilter');
        
        // Clear existing options except 'All Topics'
        topicFilter.innerHTML = '<option value="all">All Topics</option>';
        
        topics.forEach(topic => {
            const option = document.createElement('option');
            option.value = topic;
            option.textContent = topic;
            topicFilter.appendChild(option);
        });
    }
    
    filterPapers(searchTerm = '', selectedTopic = 'all') {
        this.filteredPapers = this.papers.filter(paper => {
            const matchesSearch = !searchTerm || 
                paper.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                paper.authors.join(' ').toLowerCase().includes(searchTerm.toLowerCase()) ||
                paper.summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
                paper.topic.toLowerCase().includes(searchTerm.toLowerCase());
            
            const matchesTopic = selectedTopic === 'all' || paper.topic === selectedTopic;
            
            return matchesSearch && matchesTopic;
        });
        
        // Sort by date in decreasing order (newest first)
        this.filteredPapers.sort((a, b) => new Date(b.date) - new Date(a.date));
        
        this.renderPapers();
    }
    
    renderPapers() {
        const papersGrid = document.getElementById('papersGrid');
        const noResults = document.getElementById('noResults');
        
        if (this.filteredPapers.length === 0) {
            papersGrid.style.display = 'none';
            noResults.style.display = 'block';
            return;
        }
        
        papersGrid.style.display = 'grid';
        noResults.style.display = 'none';
        
        papersGrid.innerHTML = '';
        
        this.filteredPapers.forEach(paper => {
            const paperCard = this.createPaperCard(paper);
            papersGrid.appendChild(paperCard);
        });
    }
    
    createPaperCard(paper) {
        const template = document.getElementById('paperCardTemplate');
        const card = template.content.cloneNode(true);
        
        // Fill in the data
        card.querySelector('.paper-title').textContent = paper.title;
        card.querySelector('.paper-date').textContent = new Date(paper.date).toLocaleDateString();
        card.querySelector('.paper-topic').textContent = paper.topic;
        
        // Add status with appropriate styling
        const statusElem = card.querySelector('.paper-status');
        statusElem.textContent = paper.status;
        statusElem.className = `paper-status status-${paper.status.toLowerCase().replace(/\s+/g, '-')}`;
        
        card.querySelector('.paper-authors').textContent = paper.authors.join(', ');
        
        // Handle summary with read more functionality and rich text formatting
        const summary = paper.summary;
        const previewLength = 200;
        
        const summaryPreview = card.querySelector('.summary-preview');
        const summaryFull = card.querySelector('.summary-full');
        const readMoreBtn = card.querySelector('.read-more-btn');
        
        // Format Notion's rich text blocks to HTML
        const formatRichText = (richText) => {
            if (typeof richText === 'string') {
                // Handle legacy plain text format
                return richText.split('\n\n').map(para => `<p>${para.trim()}</p>`).join('');
            }
            
            // Handle Notion's rich text format
            return richText.map(block => {
                let content = block.text.content;
                const annotations = block.annotations || {};
                
                // Apply text decorations based on annotations
                if (annotations.bold) content = `<strong>${content}</strong>`;
                if (annotations.italic) content = `<em>${content}</em>`;
                if (annotations.strikethrough) content = `<del>${content}</del>`;
                if (annotations.underline) content = `<u>${content}</u>`;
                if (annotations.code) content = `<code>${content}</code>`;
                
                return content;
            }).join('');
        
        const formattedSummary = formatRichText(summary);
        const isLong = formattedSummary.length > previewLength;
        
        if (isLong) {
            // For preview, show a shorter version
            const previewText = formattedSummary.substring(0, previewLength) + '...';
            summaryPreview.innerHTML = `<p>${previewText}</p>`;
            summaryFull.innerHTML = `<p>${formattedSummary}</p>`;
            
            readMoreBtn.addEventListener('click', () => {
                const isExpanded = summaryFull.style.display !== 'none';
                
                if (isExpanded) {
                    summaryPreview.style.display = 'block';
                    summaryFull.style.display = 'none';
                    readMoreBtn.querySelector('.read-more-text').textContent = 'Read more';
                    readMoreBtn.classList.remove('expanded');
                } else {
                    summaryPreview.style.display = 'none';
                    summaryFull.style.display = 'block';
                    readMoreBtn.querySelector('.read-more-text').textContent = 'Read less';
                    readMoreBtn.classList.add('expanded');
                }
            });
        } else {
            summaryPreview.textContent = summary;
            readMoreBtn.style.display = 'none';
        }
        
        // Set up links
        const arxivBtn = card.querySelector('.arxiv-btn');
        const pdfBtn = card.querySelector('.pdf-btn');
        
        if (paper.arxiv_id) {
            arxivBtn.href = `https://arxiv.org/abs/${paper.arxiv_id}`;
        } else {
            arxivBtn.style.display = 'none';
        }
        
        if (paper.pdf_url) {
            pdfBtn.href = paper.pdf_url;
        } else {
            pdfBtn.style.display = 'none';
        }
        
        // Share functionality
        const shareBtn = card.querySelector('.share-btn');
        shareBtn.addEventListener('click', () => {
            this.sharePaper(paper);
        });
        
        return card;
    }
    
    sharePaper(paper) {
        const url = window.location.href;
        const text = `Check out this research paper: "${paper.title}" by ${paper.authors.join(', ')}`;
        
        if (navigator.share) {
            navigator.share({
                title: paper.title,
                text: text,
                url: url
            });
        } else {
            // Fallback: copy to clipboard
            const shareText = `${text}\n${url}`;
            navigator.clipboard.writeText(shareText).then(() => {
                this.showToast('Link copied to clipboard!');
            });
        }
    }
    
    showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--primary-color);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            animation: fadeIn 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
    
    hideLoading() {
        document.getElementById('loadingSpinner').style.display = 'none';
    }
    
    showError() {
        document.getElementById('loadingSpinner').style.display = 'none';
        document.getElementById('errorMessage').style.display = 'block';
    }
}

// Initialize the website when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PapersWebsite();
});

// Add some additional utility functions
document.addEventListener('keydown', (e) => {
    // Focus search on Ctrl/Cmd + K
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('searchInput').focus();
    }
});

// Smooth scrolling for any anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});