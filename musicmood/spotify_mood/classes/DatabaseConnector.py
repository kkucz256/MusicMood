from django.utils import timezone
from ..models import Genre, SongsPlaylist, Playlist, SongArtists, Artist, Song, User, PlaylistGenre


class DatabaseConnector:
    def save_song_to_db(self, song_data):
        song, created = Song.objects.get_or_create(
            spotify_id=song_data['id'],
            defaults={
                'title': song_data['name'],
                'duration': song_data['duration_ms'] // 1000
            }
        )
        return song

    def save_artist_to_db(self, artist_data):
        artist, created = Artist.objects.get_or_create(
            spotify_artist_id=artist_data['id'],
            defaults={
                'artist': artist_data['name']
            }
        )
        return artist

    def save_song_artist_relation(self, song, artist):
        relation, created = SongArtists.objects.get_or_create(
            song=song,
            artist=artist
        )

    def save_playlist_to_db(self, playlist_name, user):
        playlist = Playlist.objects.create(
            name=playlist_name,
            user=user,
            spotify_id='',
            created_at=timezone.now()
        )
        return playlist

    def save_song_playlist_relation(self, playlist, song):
        relation, created = SongsPlaylist.objects.get_or_create(
            playlist=playlist,
            song=song
        )

    def get_user_by_spotify_id(self, spotify_id):
        try:
            user = User.objects.get(spotify_id=spotify_id)
            return user
        except User.DoesNotExist:
            return None

    def get_available_genres(self):
        genres = Genre.objects.values_list('genre', flat=True)
        available_genres = list(genres)
        return available_genres

    def get_recent_tracks_by_genre(self, user, genre, limit=2):
        recent_playlists = Playlist.objects.filter(user=user, playlistgenre__genre__genre=genre).order_by(
            '-created_at')[:limit]

        recent_tracks = set()
        for playlist in recent_playlists:
            songs_relations = SongsPlaylist.objects.filter(playlist=playlist)
            for relation in songs_relations:
                recent_tracks.add(relation.song.spotify_id)

        return recent_tracks

    def save_playlist_genre_relation(self, playlist, genre_name):
        try:
            genre = Genre.objects.get(genre=genre_name)
            PlaylistGenre.objects.get_or_create(playlist=playlist, genre=genre)
        except Genre.DoesNotExist:
            print(f"Gatunek {genre_name} nie istnieje.")

