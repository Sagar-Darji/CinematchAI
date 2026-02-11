# 🎬 CineMatch AI

> Multi-Agent Movie Recommendation System with Explainable AI

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

CineMatch AI is a production-grade movie recommendation system powered by 6 specialized AI agents working together to deliver personalized, context-aware, and explainable movie recommendations. Built with LangGraph, RAG, and multi-modal AI.

## Key Features

- **Multi-Agent Architecture**: 6 specialized agents orchestrated via LangGraph
  - Profile Analyzer (user preference extraction)
  - Content Intelligence (movie analysis + micro-genres)
  - Context-Aware (temporal/environmental context)
  - Serendipity (exploration vs exploitation)
  - Explanation (natural language reasoning)
  - Group Recommendation (multi-user fairness)

- **Multi-Modal AI**: Combines text embeddings (plot, genres) + image embeddings (posters via CLIP)

- **Explainable Recommendations**: Natural language explanations with supporting evidence

- **Group Mode**: Fair recommendations for multiple users with satisfaction guarantees

- **Context-Aware**: Adapts to time of day, day of week, mood, and viewing situation

- **Cold-Start Solution**: Interactive onboarding for new users

## Tech Stack

**100% Free & Open Source:**
- **LLM**: Ollama (Llama 3.1 70B) with MLX optimization for M4 Pro
- **Embeddings**: sentence-transformers (text), CLIP (images)
- **Vector DB**: Chroma (local, persistent)
- **Agents**: LangGraph (supervisor pattern)
- **Backend**: FastAPI (async, type-safe)
- **Frontend**: Streamlit (multi-page app)
- **Data**: MovieLens 25M + TMDB API
- **Deployment**: Hugging Face Spaces (free tier)

## Architecture

```
User Request → Supervisor Agent
    ├─→ Profile Analyzer → User preferences & patterns
    ├─→ Content Intelligence → Movie analysis & micro-genres
    ├─→ Context-Aware → Temporal/environmental context
    ↓
RAG Retrieval → Top-K candidates from Chroma DB
    ↓
Serendipity Agent → Diversity optimization
    ↓
Explanation Agent → Natural language reasoning
    ↓
Final Recommendations + Explanations
```

## Quick Start

### Prerequisites

- Python 3.10+
- 16GB+ RAM (24GB recommended)
- Ollama installed

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/cinematch-ai.git
cd cinematch-ai
```

2. **Install dependencies**
```bash
# Using pip
pip install -r requirements.txt

# Or using Poetry
poetry install
```

3. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys (TMDB, Groq backup)
```

4. **Install Ollama and pull models**
```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models (optimized for M4 Pro with MLX)
ollama pull llama3.1:70b
ollama pull llama3.1:8b
```

5. **Download data and build embeddings**
```bash
# Download MovieLens dataset and TMDB metadata
python scripts/setup_data.py

# Generate embeddings (takes ~30 minutes)
python scripts/build_embeddings.py

# Build vector database
python scripts/build_vectordb.py
```

6. **Run the application**
```bash
# Start FastAPI backend (Terminal 1)
./scripts/run_api.sh
# Or manually: uvicorn src.api.main:app --reload --port 8000

# In another terminal, start Streamlit UI (Terminal 2)
./scripts/run_ui.sh
# Or manually: streamlit run src/ui/app.py
```

7. **Open your browser**
- Streamlit UI: http://localhost:8501
- API docs: http://localhost:8000/docs

## Project Structure

```
cinematch-ai/
├── config/              # Configuration files
├── data/                # Data storage
│   ├── raw/             # MovieLens + TMDB
│   ├── processed/       # Cleaned data
│   ├── embeddings/      # Pre-computed embeddings
│   └── vectordb/        # Chroma DB
├── src/
│   ├── agents/          # Multi-agent system
│   ├── core/            # Embeddings, vectordb, models
│   ├── data_pipeline/   # ETL and preprocessing
│   ├── services/        # Business logic
│   ├── api/             # FastAPI backend
│   ├── ui/              # Streamlit frontend
│   └── utils/           # Utilities
├── scripts/             # Setup and deployment scripts
├── tests/               # Test suite
├── evaluation/          # Metrics and benchmarks
└── docs/                # Documentation
```

## API Endpoints

```bash
# Get personalized recommendations
POST /api/v1/recommendations
{
  "user_id": "user_123",
  "context": {"time_of_day": "evening", "mood": "relaxed"},
  "num_recommendations": 10
}

# Group recommendations
POST /api/v1/recommendations/group
{
  "user_ids": ["user_1", "user_2", "user_3"],
  "aggregation_strategy": "multiplicative"
}

# Cold-start onboarding
POST /api/v1/users/onboard
{
  "user_id": "new_user",
  "favorite_movies": ["The Matrix", "Inception"]
}
```

## Evaluation Metrics

**Offline Evaluation (MovieLens Test Set):**
- Hit Rate@10: > 0.30
- NDCG@10: > 0.25
- Intra-list Diversity: > 0.60
- Coverage: > 20%

**Performance:**
- API Response Time (P95): < 2 seconds
- Memory Usage: < 14GB
- Error Rate: < 1%

## Development

```bash
# Run tests
pytest tests/ -v

# Run specific test suite
pytest tests/unit/agents/ -v

# Run evaluation
python evaluation/benchmarks/offline_eval.py

# Format code
black src/
isort src/

# Type checking
mypy src/
```

## Deployment

### Hugging Face Spaces

```bash
# Deploy to HF Spaces
python scripts/deploy_hf_space.py
```

See [deployment/huggingface/README.md](deployment/huggingface/README.md) for detailed instructions.

## Documentation

- [Architecture](docs/architecture.md) - System design and agent responsibilities
- [API Reference](docs/api_reference.md) - Endpoint documentation
- [User Guide](docs/user_guide.md) - How to use the system
- [Deployment Guide](docs/deployment_guide.md) - Deployment instructions

## Roadmap

- [x] Phase 1-2: Foundation & Data Pipeline (Weeks 1-4)
- [x] Phase 3-4: Embeddings & Vector Database (Weeks 5-8)
- [x] Phase 5-6: All 6 Agents + Supervisor (Weeks 5-8)
- [x] Phase 7: LangGraph Workflow Orchestration (Week 9)
- [x] Phase 8: FastAPI Backend (Week 10)
- [x] Phase 9: Streamlit Frontend UI (Week 10)
- [ ] Phase 10: Evaluation & Optimization (Week 11)
- [ ] Phase 11: Deployment & Documentation (Week 12)

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [MovieLens Dataset](https://grouplens.org/datasets/movielens/)
- [TMDB API](https://www.themoviedb.org/documentation/api)
- [LangChain & LangGraph](https://www.langchain.com/)
- [Ollama](https://ollama.ai/)
- [Chroma DB](https://www.trychroma.com/)

## Contact

For questions or feedback:
- GitHub Issues: [https://github.com/yourusername/cinematch-ai/issues](https://github.com/yourusername/cinematch-ai/issues)
- Email: your.email@example.com

---

Built with ❤️ using 100% free and open-source tools
