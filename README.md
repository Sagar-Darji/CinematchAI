---
title: CineMatch AI
emoji: 🎬
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
license: mit
---

# 🎬 CineMatch AI

**Multi-Agent Movie Recommendation System with RAG & Multi-Modal AI**

## What is CineMatch AI?

CineMatch AI is a production-grade movie recommendation system powered by **6 specialized AI agents** working together to deliver personalized, context-aware, and explainable recommendations.

### ✨ Key Features

- 🤖 **Multi-Agent System**: 6 specialized agents orchestrated via LangGraph
- 🔍 **RAG Architecture**: Vector similarity search with ChromaDB
- 🎨 **Multi-Modal AI**: Combines text (plot) + image (poster) embeddings
- 🌍 **Context-Aware**: Adapts to your mood, time, and viewing situation
- 💡 **Explainable**: Natural language reasoning for each recommendation
- 👥 **Group Mode**: Fair recommendations for multiple users

## How It Works

### The 6 AI Agents

1. **Profile Analyzer** - Understands your taste from rating history
2. **Content Intelligence** - Analyzes movie themes and micro-genres
3. **Context-Aware** - Considers time of day, mood, companion
4. **Serendipity** - Prevents filter bubbles, adds diversity
5. **Explanation** - Generates natural language reasoning
6. **Group Recommendation** - Optimizes for fairness when watching with others

### Architecture

```
Your Request
    ↓
Streamlit UI → FastAPI → Multi-Agent Workflow
    ↓
6 Agents Working Together:
  Profile → Context → RAG Retrieval → Content Analysis
  → Serendipity → Explanation → Group (if needed)
    ↓
Personalized Recommendations + Explanations
```

## 🚀 Getting Started

### First Time Users

1. **Onboard**: Rate 5 movies to create your profile
2. **Get Recommendations**: Receive personalized suggestions
3. **Provide Feedback**: Rate recommendations to improve your profile

### Existing Users

1. Enter your username
2. Set your current context (mood, time, companion)
3. Get instant personalized recommendations

## 📊 Technology Stack

- **LLM**: Groq API (Llama 3.1 70B)
- **Embeddings**: sentence-transformers + CLIP
- **Vector DB**: ChromaDB (HNSW indexing)
- **Orchestration**: LangGraph
- **Backend**: FastAPI
- **Frontend**: Streamlit
- **Dataset**: MovieLens 25M (62K movies)

## 🎯 Features

### Personalized Recommendations
- Analyzes your viewing history
- Detects temporal patterns
- Calculates psychological metrics

### Context-Aware
- Morning vs evening preferences
- Weekday vs weekend mood
- Solo vs social viewing

### Explainable AI
- "Why this movie?" explanations
- Multi-faceted reasoning
- Transparent recommendations

### Group Mode
- Fair recommendations for 2+ people
- Multiple aggregation strategies
- Conflict detection

## 📈 Performance

- **Response Time**: < 2 seconds (P95)
- **Vector Retrieval**: < 300ms
- **Recommendation Quality**: Hit Rate@10 > 0.30
- **Diversity**: Intra-list diversity > 0.60

## 🔬 Technical Details

### Multi-Modal Embeddings
- **Text**: Plot, genres, themes (768-dim)
- **Image**: Poster aesthetics (512-dim)
- **Hybrid**: 70% text + 30% image fusion

### RAG Architecture
- ChromaDB with HNSW indexing
- Fast similarity search
- Hybrid text+image retrieval

### Evaluation
- 15+ metrics (accuracy, diversity, explainability)
- Benchmarked against baselines
- Offline evaluation on MovieLens test set

## 📚 Documentation

- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **API Reference**: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Deployment**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 🏆 Project Stats

- **Lines of Code**: 10,000+
- **Files**: 70+
- **Agents**: 7 (6 specialized + supervisor)
- **API Endpoints**: 7
- **Documentation**: 1,450+ lines

## 💻 Source Code

Full source code available on GitHub:
**[github.com/yourusername/cinematch-ai](https://github.com/yourusername/cinematch-ai)**

## 🎓 Built For

Portfolio project demonstrating:
- Multi-agent systems (LangGraph)
- RAG architecture (ChromaDB)
- Multi-modal AI (text + image)
- Production engineering
- Full-stack development

Perfect for MAANG-level technical interviews!

## 📄 License

MIT License - See [LICENSE](LICENSE)

## 🙏 Acknowledgments

- MovieLens (GroupLens Research)
- TMDB API
- Groq API
- LangChain/LangGraph
- ChromaDB

---

<p align="center">
  <strong>Built with ❤️ for movie lovers</strong><br>
  <em>Using 100% free and open-source tools</em>
</p>
