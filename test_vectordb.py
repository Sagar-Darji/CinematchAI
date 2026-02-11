import sys
sys.path.insert(0, '/Users/sagardarji/CinematchAI')

from src.core.vectordb import get_chroma_client
import numpy as np
import pandas as pd

# Load data
embeddings = np.load('data/embeddings/movie_hybrid_embeddings.npy')
movies_df = pd.read_parquet('data/processed/movies_enriched.parquet')

# Connect to database
client = get_chroma_client(collection_name='cinematch_movies')
client.get_collection('cinematch_movies')

print('🔍 Vector Database Test')
print('=' * 60)
print(f'Total movies indexed: {client.count()}')
print()

# Test: Find movies similar to Toy Story
print('Finding movies similar to Toy Story...')
results = client.similarity_search(embeddings[0], k=5)

for i, result in enumerate(results, 1):
    movie_id = result['metadata']['movieId']
    movie = movies_df[movies_df['movieId'] == movie_id].iloc[0]
    title = movie.get('title_clean', movie.get('title'))
    genres = result['metadata'].get('tmdb_genres', 'N/A')
    distance = result['distance']
    
    print(f'{i}. {title}')
    print(f'   Genres: {genres}')
    print(f'   Similarity: {1 - distance:.3f}')
    print()

print('✅ RAG system is working!')
