from src.services.movie_service import MovieService


def test_parse_tmdb_search_result_for_tv_uses_tv_fields():
    service = MovieService()

    result = service._parse_tmdb_search_result(
        {
            "id": 1399,
            "name": "Game of Thrones",
            "original_name": "Game of Thrones",
            "overview": "Seven kingdoms fight for control.",
            "genre_ids": [10759, 18, 10765],
            "first_air_date": "2011-04-17",
            "vote_average": 8.4,
            "vote_count": 24000,
            "poster_path": "/u3bZgnGQ9T01sWNhyveQz0wH0Hl.jpg",
            "original_language": "en",
        },
        media_type="tv",
    )

    assert result is not None
    assert result.metadata.media_type == "tv"
    assert result.metadata.title == "Game of Thrones"
    assert result.metadata.year == 2011
    assert result.metadata.genres == ["Action & Adventure", "Drama", "Sci-Fi & Fantasy"]


def test_parse_tmdb_media_for_tv_includes_seasons_and_creator():
    service = MovieService()

    result = service._parse_tmdb_media(
        {
            "id": 1399,
            "name": "Game of Thrones",
            "original_name": "Game of Thrones",
            "overview": "Seven kingdoms fight for control.",
            "tagline": "Winter is coming.",
            "genres": [
                {"id": 10759, "name": "Action & Adventure"},
                {"id": 18, "name": "Drama"},
            ],
            "first_air_date": "2011-04-17",
            "vote_average": 8.4,
            "vote_count": 24000,
            "popularity": 320.0,
            "poster_path": "/u3bZgnGQ9T01sWNhyveQz0wH0Hl.jpg",
            "backdrop_path": "/suopoADq0k8YZr4dQXcU6pToj6s.jpg",
            "original_language": "en",
            "spoken_languages": [{"english_name": "English", "iso_639_1": "en"}],
            "episode_run_time": [55],
            "created_by": [{"name": "David Benioff"}, {"name": "D. B. Weiss"}],
            "number_of_seasons": 8,
            "number_of_episodes": 73,
            "seasons": [
                {
                    "season_number": 1,
                    "name": "Season 1",
                    "episode_count": 10,
                    "air_date": "2011-04-17",
                    "poster_path": "/kMTcwNRfFKCZ0O2OaBZS0nZ2AIe.jpg",
                },
                {
                    "season_number": 2,
                    "name": "Season 2",
                    "episode_count": 10,
                    "air_date": "2012-04-01",
                    "poster_path": "/5f0F6fms7QOov3s4ulAeHvt4l7s.jpg",
                },
            ],
            "credits": {
                "cast": [{"name": "Emilia Clarke"}, {"name": "Kit Harington"}],
                "crew": [{"job": "Executive Producer", "name": "David Benioff"}],
            },
            "status": "Ended",
        },
        media_type="tv",
    )

    assert result.metadata.media_type == "tv"
    assert result.metadata.title == "Game of Thrones"
    assert result.metadata.creator == "David Benioff, D. B. Weiss"
    assert result.metadata.runtime == 55
    assert result.metadata.season_count == 8
    assert result.metadata.episode_count == 73
    assert len(result.metadata.seasons) == 2
    assert result.metadata.seasons[0].season_number == 1
    assert result.metadata.seasons[0].episode_count == 10
