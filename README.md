# Dr. Paper

![Dr. Paper](docs/images/dr-paper.png)

A command-line tool for analyzing research papers using RAG (Retrieval-Augmented Generation). Built with LangChain, FAISS, and Ollama.

## Features

- Analyze PDF research papers with local LLMs
- Fetch trending papers from arXiv (last 14 days) 
- Multiple prompt types (blog, technical, summary, comparison)
- Optional Notion database integration

## Quick Start

### 1. Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running
- At least one language model pulled (e.g., `ollama pull llama3.1:8b`)

### 2. Setup

```bash
# Clone or download this project
cd research-paper-rag

# Create virtual environment
python -m venv .agentic

# Activate virtual environment
source .agentic/bin/activate  # macOS/Linux
# or
.agentic\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Make the wrapper script executable
chmod +x doctor_paper
```

### 3. Add Your Papers

Create a `papers` directory and add your PDF research papers:

```bash
mkdir papers
# Copy your PDF files to the papers/ directory
cp /path/to/your/paper.pdf papers/
```

### 4. Usage

The `doctor_paper` wrapper script provides an easy interface:

```bash
# Basic usage with default blog prompt
./doctor_paper papers/your_paper.pdf

# Use different prompt types
./doctor_paper -p tech papers/your_paper.pdf     # Technical analysis
./doctor_paper -p summary papers/your_paper.pdf  # Comprehensive summary
./doctor_paper -p compare papers/your_paper.pdf  # Compare with existing work

# Use different models
./doctor_paper -m mistral papers/your_paper.pdf
./doctor_paper -m llama2 papers/your_paper.pdf

# Custom queries
./doctor_paper papers/your_paper.pdf "Explain the methodology in simple terms"

# Combine options
./doctor_paper -m llama3.1:8b -p tech papers/attention_paper.pdf
```

## Prompt Types

| Type | Description | Use Case |
|------|-------------|----------|
| `blog` | Blog-style summary with problem/solution/impact | General audience, clear explanations |
| `summary` | Comprehensive academic summary | Detailed understanding, research purposes |
| `tech` | Technical analysis of methodology | Implementation details, technical depth |
| `compare` | Comparison with existing work | Research context, positioning |

## Examples

```bash
# Analyze a transformer paper for a blog post
./doctor_paper papers/attention_is_all_you_need.pdf

# Get technical details about a machine learning paper
./doctor_paper -p tech papers/deep_learning_paper.pdf

# Compare a new approach with existing methods
./doctor_paper -p compare papers/novel_approach.pdf

# Use a specific model for analysis
./doctor_paper -m llama3.1:8b papers/research_paper.pdf
```

## Project Structure

```
dr-paper/
├── doctor_paper              # Main wrapper script
├── src/                     # Python source code
│   ├── research_paper_rag.py    # Core RAG analysis
│   ├── fetch.py                 # Paper fetching (trending)
│   ├── fetch_and_notion.py      # Notion integration
│   └── debug.py                 # Debug utilities
├── docs/                    # Documentation
│   └── images/             
│       └── dr-paper.png         # Project logo
├── papers/                  # Place your PDF papers here
│   ├── paper1.pdf
│   └── paper2.pdf
├── pdf/                     # Auto-downloaded papers
├── .data/                   # Cached FAISS indexes (auto-created)
│   ├── faiss_index_paper1/
│   └── faiss_index_paper2/
├── .agentic/               # Python virtual environment
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Automated Paper Pipeline

Fetch trending papers automatically:

```bash
cd src/
python fetch_and_notion.py  # Store in Notion database
python fetch.py             # Print trending papers
```

## Configuration

### Environment Setup

The script automatically:
- Activates the `.agentic` virtual environment
- Uses the configured Python interpreter
- Manages FAISS index caching in `.data/`

### Ollama Models

Ensure you have models installed:

```bash
# Popular models for research analysis
ollama pull llama3.1:8b      # Good balance of speed/quality
ollama pull mistral          # Fast and efficient
ollama pull llama2           # Alternative option
ollama pull codellama        # For code-heavy papers
```


## License

This project is for research and educational purposes. Ensure you have proper rights to analyze any papers you process.

---

**Happy Research!**
