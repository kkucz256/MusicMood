import os
import random
import sys
import base64
import hashlib
from django.utils import timezone
import time
import requests
import urllib.parse
from . import Fuzzy
from .DatabaseConnector import DatabaseConnector
from django.core.cache import cache
from ..models import LikedSongs, Playlist, Genre


class SpotifyAPI:
    CLIENT_ID = 'd596c03aba8648328d29072f30f046bc'
    REDIRECT_URI = 'http://127.0.0.1:8000/callback'
    SCOPE = 'user-read-private user-read-email user-library-read user-library-modify playlist-read-private playlist-modify-public playlist-modify-private streaming user-read-playback-state user-modify-playback-state'
    AUTH_URL = 'https://accounts.spotify.com/authorize'
    TOKEN_URL = 'https://accounts.spotify.com/api/token'

    def __init__(self):
        self.db_connector = DatabaseConnector()

    @staticmethod
    def generate_code_verifier():
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
        return code_verifier

    @staticmethod
    def generate_code_challenge(code_verifier):
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).decode(
            'utf-8').rstrip('=')
        return code_challenge

    def get_authorization_url(self, code_challenge):
        params = {
            'response_type': 'code',
            'client_id': self.CLIENT_ID,
            'scope': self.SCOPE,
            'code_challenge_method': 'S256',
            'code_challenge': code_challenge,
            'redirect_uri': self.REDIRECT_URI
        }
        url_params = urllib.parse.urlencode(params)
        return f"{self.AUTH_URL}?{url_params}"

    def get_token(self, code, code_verifier):
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.REDIRECT_URI,
            'client_id': self.CLIENT_ID,
            'code_verifier': code_verifier
        }
        response = requests.post(self.TOKEN_URL, data=data)
        return response.json()

    def get_user_info(self, access_token):
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://api.spotify.com/v1/me', headers=headers)
        return response.json()

    def get_user_playlists(self, access_token):
        url = 'https://api.spotify.com/v1/me/playlists'
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()['items']
        else:
            print(f"Nie udało się uzyskać playlisty: {response.status_code}")
            return None

    def get_audio_features(self, access_token, track_ids):
        url = f'https://api.spotify.com/v1/audio-features'
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {'ids': ','.join(track_ids)}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()['audio_features']
        else:
            print(f"Nie udało się otrzymać informacji o utworze: {response.status_code}")
            return None

    def get_track_info(self, access_token, track_id):
        url = f'https://api.spotify.com/v1/tracks/{track_id}'
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Nie udało się pobrać informacji o utworze: {response.status_code}")
            retry_after = int(response.headers.get("Retry-After", 1))
            print(f"Zbyt wiele zapytań. Ponawianie za {retry_after} sekund.")
            return None

    def get_available_genres(self):
        return self.db_connector.get_available_genres()

    def search_tracks_by_features(self, access_token, energy, valence, tempo, loudness, danceability, length_min,
                                  length_max, genres, track_count):
        headers = {'Authorization': f'Bearer {access_token}'}
        url = 'https://api.spotify.com/v1/recommendations'

        length_min_ms = length_min * 60 * 1000 if length_min is not None else 0
        length_max_ms = length_max * 60 * 1000 if length_max is not None else 9999999

        params = {
            'limit': track_count,
            'seed_genres': ','.join(genres),
            'target_energy': energy,
            'target_valence': valence,
            'target_tempo': tempo,
            'target_loudness': loudness,
            'target_danceability': danceability,
            'min_duration_ms': length_min_ms,
            'max_duration_ms': length_max_ms,
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            tracks = response.json()['tracks']
            track_ids = [track['id'] for track in tracks]

            return track_ids
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            print(f"Zbyt wiele zapytań. Ponawianie za {retry_after} sekund.")
            time.sleep(retry_after)
            return []
        else:
            print(f"Nie udało się znaleźć utworów: {response.status_code} - {response.text}")
            return []

    def generate_playlist_v2(self, access_token, mood_value, length_min, length_max, genres, genre_percentages,
                             playlist_name, playlist_description, track_count=10, custom_params=None,
                             overshoot_factor=1.5):
        if mood_value is not None:
            fuzzy = Fuzzy.Fuzzy()
            params = fuzzy.compute_recommendation(mood_value)
            fuzzy.print_results(mood_value)
            fuzzy.print_membership(mood_value)

            target_energy = params['energy']
            target_valence = params['valence']
            target_tempo = params['tempo']
            target_loudness = params['loudness']
            target_danceability = params['danceability']
        else:
            target_energy = custom_params['energy']
            target_valence = custom_params['valence']
            target_tempo = custom_params['tempo']
            target_loudness = custom_params['loudness']
            target_danceability = custom_params['danceability']

        track_data = []

        user_info = self.get_user_info(access_token)
        user = self.db_connector.get_user_by_spotify_id(user_info['id'])

        for genre, percentage in zip(genres, genre_percentages):
            genre_track_count = max(1, round(track_count * (percentage / 100)))

            found_tracks = False
            filtered_genre_track_ids = set()

            while not found_tracks:
                expanded_track_count = int(genre_track_count * overshoot_factor)
                recent_tracks_by_genre = self.db_connector.get_recent_tracks_by_genre(user, genre, limit=2)

                genre_track_ids = self.search_tracks_by_features(
                    access_token, target_energy, target_valence, target_tempo, target_loudness, target_danceability,
                    length_min, length_max, [genre], expanded_track_count
                )
                new_tracks = [track_id for track_id in genre_track_ids if track_id not in recent_tracks_by_genre]
                filtered_genre_track_ids.update(new_tracks)

                if len(filtered_genre_track_ids) >= genre_track_count:
                    found_tracks = True
                else:
                    target_energy *= 0.9
                    target_tempo *= 0.9
                    overshoot_factor += 0.5

                    if overshoot_factor > 3.0:
                        break

            track_data.extend((track_id, genre) for track_id in filtered_genre_track_ids)

        if len(track_data) > track_count:
            track_data = random.sample(track_data, track_count)
        elif len(track_data) < track_count:
            print(f"Brakuje {track_count - len(track_data)} utworów po pierwszym przefiltrowaniu.")

        if not track_data:
            print("Nie znaleziono utworów spełniających kryteria.")
            return None

        random.shuffle(track_data)
        self.create_playlist(access_token, playlist_name, track_data, playlist_description, genres)

    def create_playlist(self, access_token, playlist_name, track_data, combined_seeds, playlist_description="", genres=[]):
        user_info = self.get_user_info(access_token)
        user_id = user_info['id']
        user = self.db_connector.get_user_by_spotify_id(user_id)
        playlist = self.db_connector.save_playlist_to_db(playlist_name, user, combined_seeds)

        if not playlist:
            print(f"Nie udało się zapisać playlisty {playlist_name}")
            return

        url = f'https://api.spotify.com/v1/users/{user_id}/playlists'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        data = {
            'name': playlist_name,
            'description': playlist_description,
            'public': False
        }
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 201:
            spotify_playlist_id = response.json()['id']

            playlist.spotify_id = spotify_playlist_id
            playlist.save()

            track_uris = [f'spotify:track:{track_id}' for track_id, _ in track_data]
            add_tracks_url = f'https://api.spotify.com/v1/playlists/{spotify_playlist_id}/tracks'
            data = {'uris': track_uris}
            add_tracks_response = requests.post(add_tracks_url, headers=headers, json=data)

            if add_tracks_response.status_code == 201:
                print(f"Utwory zostały pomyślnie dodane do playlisty '{playlist_name}' na Spotify.")

                for track_id, genre in track_data:
                    track_info = self.get_track_info(access_token, track_id)
                    if not track_info:
                        continue

                    song = self.db_connector.save_song_to_db(track_info, genre)

                    for artist_data in track_info['artists']:
                        artist = self.db_connector.save_artist_to_db(artist_data)
                        self.db_connector.save_song_artist_relation(song, artist)

                    self.db_connector.save_song_playlist_relation(playlist, song)

                for genre_name in genres:
                    self.db_connector.save_playlist_genre_relation(playlist, genre_name)
            else:
                print(
                    f"Nie udało się dodać utworów do playlisty na Spotify: {add_tracks_response.status_code} - {add_tracks_response.text}")
        else:
            print(f"Nie udało się stworzyć playlisty na Spotify: {response.status_code} - {response.text}")

    def search_tracks_by_features_v3(self, access_token, energy, valence, tempo, loudness, danceability, length_min,
                                     length_max, seed_genre, track_seeds, track_count, min_popularity=40):
        headers = {'Authorization': f'Bearer {access_token}'}
        url = 'https://api.spotify.com/v1/recommendations'

        length_min_ms = length_min * 60 * 1000 if length_min is not None else 0
        length_max_ms = length_max * 60 * 1000 if length_max is not None else 9999999

        params = {
            'limit': track_count,
            'seed_genres': seed_genre,
            'seed_tracks': ','.join(track_seeds),
            'target_energy': energy,
            'target_valence': valence,
            'target_tempo': tempo,
            'target_loudness': loudness,
            'target_danceability': danceability,
            'min_duration_ms': length_min_ms,
            'max_duration_ms': length_max_ms,
            'min_popularity': min_popularity
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            tracks = response.json().get('tracks', [])
            track_ids = [track['id'] for track in tracks]
            return track_ids
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            print(f"Too many requests. Retrying in {retry_after} seconds.")
            time.sleep(retry_after)
            return []
        else:
            print(f"Failed to find tracks: {response.status_code} - {response.text}")
            return []

    def generate_playlist_v3(self, access_token, mood_value, length_min, length_max, genres, genre_percentages,
                             playlist_name, playlist_description, track_count=10, custom_params=None):
        if mood_value is not None:
            fuzzy = Fuzzy.Fuzzy()
            params = fuzzy.compute_recommendation(mood_value)
            fuzzy.print_results(mood_value)
            fuzzy.print_membership(mood_value)

            target_energy = params['energy']
            target_valence = params['valence']
            target_tempo = params['tempo']
            target_loudness = params['loudness']
            target_danceability = params['danceability']
        else:
            target_energy = custom_params['energy']
            target_valence = custom_params['valence']
            target_tempo = custom_params['tempo']
            target_loudness = custom_params['loudness']
            target_danceability = custom_params['danceability']

        track_data = []

        user_info = self.get_user_info(access_token)
        user = self.db_connector.get_user_by_spotify_id(user_info['id'])

        all_seeds = []

        for genre, percentage in zip(genres, genre_percentages):
            genre_track_count = max(1, round(track_count * (percentage / 100)))
            print(f"[DEBUG] Genre: {genre}, Percentage: {percentage}%, Track Count: {genre_track_count}")

            recent_songs_full = self.db_connector.get_recent_tracks_by_genre(user, genre, limit=5)
            recent_songs = [song.spotify_id for song in recent_songs_full]
            genre_id = Genre.objects.get(genre=genre).genre_id
            songs_filtered_by_genre = [song for song in recent_songs_full if song.genre_id == genre_id]
            recent_playlists = self.db_connector.get_recent_playlists_by_genre(user, genre, limit=5)

            track_seeds = []

            if recent_songs:
                liked_songs = list(
                    LikedSongs.objects.filter(user=user, song__genre__genre=genre).values_list('song__spotify_id',
                                                                                               flat=True))
                if liked_songs:
                    for playlist in recent_playlists:
                        playlist_seed = playlist.seed

                        for song in liked_songs[:]:
                            if song in playlist_seed:
                                liked_songs.remove(song)

                    if len(liked_songs) > 0:
                        seed_track = random.choice(liked_songs)
                        track_seeds = [seed_track]
                    else:
                        seed_track = random.choice([song.spotify_id for song in songs_filtered_by_genre])
                        track_seeds = [seed_track]

                    seed_genre = genre
                else:
                    seed_track = random.choice([song.spotify_id for song in songs_filtered_by_genre])
                    track_seeds = [seed_track]
                    seed_genre = genre
            else:
                track_seeds = []
                seed_genre = genre

            seed_combination = f"{','.join(track_seeds)},{seed_genre}" if track_seeds else seed_genre
            all_seeds.append(seed_combination)

            print(f"[DEBUG] Seed combination for genre {genre}: {seed_combination}")

            genre_track_ids = self.search_tracks_by_features_v3(
                access_token, target_energy, target_valence, target_tempo, target_loudness, target_danceability,
                length_min, length_max, seed_genre, track_seeds, genre_track_count
            )

            print(f"[DEBUG] Found {len(genre_track_ids)} tracks for genre {genre}")

            track_data.extend((track_id, genre) for track_id in genre_track_ids)

        print(f"[DEBUG] Total tracks before shuffling: {len(track_data)}")

        if len(track_data) > track_count:
            track_data = random.sample(track_data, track_count)
        elif len(track_data) < track_count:
            print(f"[DEBUG] Missing {track_count - len(track_data)} tracks after filtering.")

        if not track_data:
            print("[DEBUG] No tracks found matching the criteria.")
            return None

        random.shuffle(track_data)

        combined_seeds = ";".join(all_seeds)

        print(f"[DEBUG] Combined seeds for playlist: {combined_seeds}")

        self.create_playlist(access_token, playlist_name, track_data, combined_seeds, playlist_description, genres)




