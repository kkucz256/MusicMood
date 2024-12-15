from django.core.exceptions import MultipleObjectsReturned
from django.utils import timezone
from ..models import Genre, SongsPlaylist, Playlist, SongArtists, Artist, Song, User, PlaylistGenre, LikedSongs


class DatabaseConnector:
    def save_song_to_db(self, song_data, genre_name):
        try:
            genre = Genre.objects.get(genre=genre_name)
        except Genre.DoesNotExist:
            print(f"Gatunek '{genre_name}' nie istnieje.")
            return None

        photo_url = None
        if song_data.get('album') and song_data['album'].get('images') and len(song_data['album']['images']) > 0:
            photo_url = song_data['album']['images'][0]['url']

        song, created = Song.objects.get_or_create(
            spotify_id=song_data['id'],
            defaults={
                'title': song_data['name'],
                'duration': song_data['duration_ms'] // 1000,
                'genre_id': genre.genre_id,
                'photo_url': photo_url
            }
        )

        if not created and not song.photo_url:
            song.photo_url = photo_url
            song.save()

        return song

    def save_artist_to_db(self, artist_data):
        try:
            artist, created = Artist.objects.get_or_create(
                spotify_artist_id=artist_data['id'],
                defaults={'artist': artist_data['name']}
            )
        except MultipleObjectsReturned:
            duplicates = Artist.objects.filter(spotify_artist_id=artist_data['id'])
            primary_artist = duplicates.first()
            duplicates.exclude(id=primary_artist.id).delete()
            return primary_artist

        return artist

    def save_song_artist_relation(self, song, artist):
        relation, created = SongArtists.objects.get_or_create(
            song=song,
            artist=artist
        )

    def save_playlist_to_db(self, playlist_name, user, seeds):

        playlist = Playlist.objects.create(
            name=playlist_name,
            user=user,
            spotify_id='',
            created_at=timezone.now(),
            seed=seeds
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
                recent_tracks.add(relation.song)

        return recent_tracks

    def save_playlist_genre_relation(self, playlist, genre_name):
        try:
            genre = Genre.objects.get(genre=genre_name)
            PlaylistGenre.objects.get_or_create(playlist=playlist, genre=genre)
        except Genre.DoesNotExist:
            print(f"Gatunek {genre_name} nie istnieje.")

    def get_recent_playlists_by_genre(self, user, genre, limit=2):
        recent_playlists = Playlist.objects.filter(user=user, playlistgenre__genre__genre=genre).order_by(
            '-created_at')[:limit]

        return recent_playlists
