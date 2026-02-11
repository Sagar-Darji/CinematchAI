import sys
sys.path.insert(0, '/Users/sagardarji/CinematchAI')

from src.agents.profile_analyzer import get_profile_analyzer_agent
import pandas as pd
from config.settings import get_settings

# Get a user with ratings
settings = get_settings()
ratings_df = pd.read_parquet(settings.processed_data_dir / "ratings.parquet")

# Find a user with substantial ratings
user_counts = ratings_df.groupby("userId").size()
test_user_id = str(user_counts[user_counts >= 50].index[0])

print("🧠 Testing Profile Analyzer Agent")
print("=" * 60)
print(f"Test User ID: {test_user_id}")
print(f"Total Ratings: {user_counts[int(test_user_id)]}")
print()

# Initialize agent
agent = get_profile_analyzer_agent()

# Process user
state = {"user_id": test_user_id}
result = agent.process(state)

# Display profile
profile = result["user_profile"]

print("📊 User Profile Analysis:")
print("=" * 60)
print(f"Is Cold Start: {profile.is_cold_start}")
print(f"Total Ratings: {profile.total_ratings}")
print(f"Average Rating: {profile.avg_rating_given:.2f}")
print()

print("🎬 Preferences:")
print(f"  Favorite Genres: {profile.preferences.favorite_genres}")
print(f"  Favorite Directors: {profile.preferences.favorite_directors}")
print(f"  Preferred Decades: {profile.preferences.preferred_decades}")
print()

print("🧬 Psychological Profile:")
print(f"  Exploration Rate: {profile.preferences.exploration_rate:.2f} (0=safe, 1=adventurous)")
print(f"  Nostalgia Tendency: {profile.preferences.nostalgia_tendency:.2f} (0=modern, 1=classic)")
print(f"  Risk Tolerance: {profile.preferences.risk_tolerance:.2f} (0=popular only, 1=indie films)")
print()

print("⏰ Temporal Patterns:")
print(f"  Weekend Preference: {profile.temporal_patterns.weekend_preference}")
print(f"  Weekday Preference: {profile.temporal_patterns.weekday_preference}")
print(f"  Peak Viewing Time: {profile.temporal_patterns.peak_viewing_time}")
print(f"  Peak Viewing Day: {profile.temporal_patterns.peak_viewing_day}")
print()

print(f"🎯 Profile Embedding: {len(profile.profile_embedding)}-dim vector" if profile.profile_embedding else "Profile Embedding: Not generated")
print()
print("✅ Profile Analyzer Agent Working!")
