import os
import random
import sys
import base64
import hashlib
from django.utils import timezone
import time
import requests
import datetime
import urllib.parse
from . import Fuzzy
from .DatabaseConnector import DatabaseConnector
from django.core.cache import cache
from ..models import LikedSongs, Playlist, Genre


class SpotifyAPI:
    CLIENT_ID = 'd596c03aba8648328d29072f30f046bc'
    REDIRECT_URI = 'http://127.0.0.1:8000/callback'
    # REDIRECT_URI = 'http://192.168.0.81:8000/callback'
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

    def is_user_logged_in(self, access_token):
        url = 'https://api.spotify.com/v1/me'
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            print("Token wygasł lub jest nieprawidłowy.")
            return False
        else:
            print(f"Wystąpił błąd podczas sprawdzania stanu zalogowania: {response.status_code}")
            return False

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

    def create_playlist(self, access_token, playlist_name, track_data, combined_seeds, playlist_description="",
                        genres=[]):
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

    def get_recently_added_tracks(self, access_token):
        url = "https://api.spotify.com/v1/me/tracks"
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        params = {
            'limit': 10
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Nie udało się pobrać ostatnich utworów: {response.status_code}")
            return []

        recent_tracks = [item['track']['id'] for item in response.json()['items']]

        return recent_tracks

    def get_recently_added_tracks_that_match_genre(self, access_token, target_genre, track_ids):
        headers = {'Authorization': f'Bearer {access_token}'}
        url = 'https://api.spotify.com/v1/tracks'
        params = {'ids': ','.join(track_ids)}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"Nie udało się pobrać informacji o utworach: {response.status_code}")
            return []

        tracks_info = response.json()['tracks']
        artist_ids = {artist['id'] for track in tracks_info for artist in track['artists']}

        artists_url = 'https://api.spotify.com/v1/artists'
        artist_response = requests.get(artists_url, headers=headers, params={'ids': ','.join(artist_ids)})

        if artist_response.status_code != 200:
            print(f"Nie udało się pobrać informacji o artystach: {artist_response.status_code}")
            return []

        artists_info = artist_response.json()['artists']
        artist_genres = {artist['id']: artist['genres'] for artist in artists_info}
        matching_tracks = []
        for track in tracks_info:
            for artist in track['artists']:
                if target_genre.lower() in [genre.lower() for genre in artist_genres.get(artist['id'], [])]:
                    matching_tracks.append(track['id'])
                    break

        return matching_tracks

    def search_tracks_by_features_v3(self, access_token, energy, valence, tempo, loudness, danceability, length_min,
                                     length_max, track_seeds, track_count, seed_genre, min_popularity=50):
        headers = {'Authorization': f'Bearer {access_token}'}
        url = 'https://api.spotify.com/v1/recommendations'

        length_min_ms = int(length_min * 60 * 1000) if length_min is not None else 0
        length_max_ms = int(length_max * 60 * 1000) if length_max is not None else 9999999

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
        local_time = datetime.datetime.now().hour + datetime.datetime.now().minute / 60
        time_of_the_day = round(local_time, 2)
        # print(f"[DEBUG] Local time as float (time_of_the_day): {time_of_the_day}")

        if mood_value is not None:
            fuzzy = Fuzzy.Fuzzy()
            params = fuzzy.compute_recommendation(mood_value, time_of_the_day)
            fuzzy.print_results(mood_value, time_of_the_day)

            target_energy = params['energy']
            target_valence = params['valence']
            target_tempo = params['tempo']
            target_loudness = params['loudness']
            target_danceability = params['danceability']
            # print(f"[DEBUG] Computed fuzzy parameters: {params}")
        else:
            target_energy = custom_params['energy']
            target_valence = custom_params['valence']
            target_tempo = custom_params['tempo']
            target_loudness = custom_params['loudness']
            target_danceability = custom_params['danceability']
            # print(f"[DEBUG] Custom parameters: {custom_params}")

        track_data = []

        user_info = self.get_user_info(access_token)
        # print(f"[DEBUG] User info: {user_info}")
        user = self.db_connector.get_user_by_spotify_id(user_info['id'])

        all_seeds = []

        for genre, percentage in zip(genres, genre_percentages):
            genre_track_count = max(1, round(track_count * (percentage / 100)))
            # print(f"[DEBUG] Genre: {genre}, Percentage: {percentage}%, Track Count: {genre_track_count}")

            recent_songs_from_playlist_with_genre = self.db_connector.get_recent_tracks_by_genre(user, genre, limit=5)
            recent_songs = [song.spotify_id for song in recent_songs_from_playlist_with_genre]
            # print(f"[DEBUG] Recent songs for genre {genre}: {recent_songs}")

            genre_id = Genre.objects.get(genre=genre).genre_id
            songs_filtered_by_genre = [song for song in recent_songs_from_playlist_with_genre if
                                       song.genre_id == genre_id]
            # print(f"[DEBUG] Songs filtered by genre {genre}: {[song.spotify_id for song in songs_filtered_by_genre]}")

            recent_playlists = self.db_connector.get_recent_playlists_by_genre(user, genre, limit=5)
            # print(f"[DEBUG] Recent playlists for genre {genre}: {[playlist.seed for playlist in recent_playlists]}")

            recently_added_tracks = self.get_recently_added_tracks(access_token)
            track_seeds = []

            if recent_songs:
                liked_songs = list(
                    LikedSongs.objects.filter(user=user, song__genre__genre=genre).values_list('song__spotify_id',
                                                                                               flat=True))
                # print(f"[DEBUG] Liked songs for genre {genre}: {liked_songs}")
                recently_added_tracks = self.get_recently_added_tracks_that_match_genre(access_token, genre,
                                                                                        recently_added_tracks)
                # print(f"[DEBUG] Recently added songs for genre {genre}: {recently_added_tracks}")
                if liked_songs:
                    for playlist in recent_playlists:
                        playlist_seed = playlist.seed
                        for song in liked_songs[:]:
                            if song in playlist_seed:
                                liked_songs.remove(song)
                    # print(f"[DEBUG] Liked songs after filtering by recent playlists: {liked_songs}")

                    if len(liked_songs) > 0:
                        seed_track = random.choice(liked_songs)
                        track_seeds = [seed_track]
                        # print(f"[DEBUG] Selected seed_track from liked songs: {seed_track}")

                    else:
                        for playlist in recent_playlists:
                            playlist_seed = playlist.seed
                            recently_added_tracks = [song for song in recently_added_tracks if
                                                     song not in playlist_seed]
                        if len(recently_added_tracks) > 0:
                            seed_track = random.choice(recently_added_tracks)
                            track_seeds = [seed_track]
                            # print(f"[DEBUG] Selected seed_track from recent tracks: {seed_track}")
                        else:
                            seed_track = random.choice([song.spotify_id for song in songs_filtered_by_genre])
                            track_seeds = [seed_track]
                            # print(f"[DEBUG] Selected seed_track from songs filtered by genre: {seed_track}")

                elif recently_added_tracks:
                    for playlist in recent_playlists:
                        playlist_seed = playlist.seed
                        for song in recently_added_tracks[:]:
                            if song in playlist_seed:
                                recently_added_tracks.remove(song)

                    if len(recently_added_tracks) > 0:
                        seed_track = random.choice(recently_added_tracks)
                        track_seeds = [seed_track]
                        # print(f"[DEBUG] Selected seed_track from recent tracks: {seed_track}")

                    else:
                        seed_track = random.choice([song.spotify_id for song in songs_filtered_by_genre])
                        track_seeds = [seed_track]
                        # print(f"[DEBUG] Selected seed_track from songs filtered by genre: {seed_track}")
                elif len(songs_filtered_by_genre) > 0:
                    seed_track = random.choice([song.spotify_id for song in songs_filtered_by_genre])
                    track_seeds = [seed_track]

                    # print(f"[DEBUG] Selected seed_track from songs filtered by genre: {seed_track}")

                seed_genre = None
            else:
                track_seeds = []
                seed_genre = genre
                # print(f"[DEBUG] No recent songs found for genre {genre}. Using empty track_seeds.")

            current_seed = f"{','.join(track_seeds)}" if track_seeds else seed_genre
            all_seeds.append(current_seed)

            genre_track_ids = self.search_tracks_by_features_v3(
                access_token, target_energy, target_valence, target_tempo, target_loudness, target_danceability,
                length_min, length_max, track_seeds, genre_track_count, seed_genre
            )
            # print(f"[DEBUG] Found {len(genre_track_ids)} tracks for genre {genre}")

            track_data.extend((track_id, genre) for track_id in genre_track_ids)

        # print(f"[DEBUG] Total tracks before shuffling: {len(track_data)}")
        if not track_data:
            print("[DEBUG] No tracks found matching the criteria.")
            return {
                "status": "error",
                "message": "No tracks found matching the given criteria. Playlist generation failed."
            }

        if len(track_data) > track_count:
            track_data = random.sample(track_data, track_count)
            print(f"[DEBUG] Track data after sampling to match track_count: {track_data}")

        elif len(track_data) < track_count:
            missing_tracks = track_count - len(track_data)
            print(f"[DEBUG] Missing {missing_tracks} tracks after filtering.")
            random.shuffle(track_data)
            combined_seeds = ";".join(all_seeds)
            print(f"[DEBUG] Combined seeds for playlist: {combined_seeds}")
            self.create_playlist(access_token, playlist_name, track_data, combined_seeds, playlist_description, genres)
            return {
                "status": "warning",
                "message": f"Playlista posiada mniej utworów niż zostało wpisane. Brakuje {missing_tracks} utworów, "
                           f"w celu polepszenia algorytmu spróbuj ponownie wygenerować playlistę,"
                           f"zmienić parametry systemu, bądź dodać kilka utworów do polubionych.",
                "track_count": len(track_data)
            }

        random.shuffle(track_data)
        combined_seeds = ";".join(all_seeds)
        print(f"[DEBUG] Combined seeds for playlist: {combined_seeds}")

        self.create_playlist(access_token, playlist_name, track_data, combined_seeds, playlist_description, genres)
        return {
            "status": "success",
            "message": "Udało się stworzyć playlistę!",
            "track_count": len(track_data)
        }
