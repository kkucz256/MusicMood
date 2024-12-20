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
    #REDIRECT_URI = 'http://192.168.0.80:8000/callback'
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

        try:
            user_info = response.json()
            return user_info
        except ValueError as e:
            return {"error": "Błąd przy dekodowaniu JSON", "response_text": response.text}

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
                                     length_max, track_seeds, track_count, seed_genre, min_popularity=40):
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
            print(f"Za dużo prób. Ponawiam za {retry_after} sekund.")
            time.sleep(retry_after)
            return []
        else:
            print(f"Nie udało się znaleźć utworów: {response.status_code} - {response.text}")
            return []

    def generate_playlist_v3(self, access_token, mood_value, length_min, length_max, genres, genre_percentages,
                             playlist_name, playlist_description, track_count=10, custom_params=None, selected_song_ids=None):
        local_time = datetime.datetime.now().hour + datetime.datetime.now().minute / 60
        time_of_the_day = round(local_time, 2)

        if mood_value is not None:
            fuzzy = Fuzzy.Fuzzy()
            params = fuzzy.compute_recommendation(mood_value, time_of_the_day)
            fuzzy.print_results(mood_value, time_of_the_day)

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

        if selected_song_ids:
            genre = genres[0]
            recent_songs_from_playlist_with_genre = self.db_connector.get_recent_tracks_by_genre(user, genre, limit=5)
            recent_songs = [song.spotify_id for song in recent_songs_from_playlist_with_genre]
            if recent_songs:
                choice = random.choice(recent_songs)
                selected_song_ids.append(choice)
                genre = None
            else:
                all_seeds.append(genre)

            found_tracks = self.search_tracks_by_features_v3(
                access_token, target_energy, target_valence, target_tempo, target_loudness, target_danceability,
                length_min, length_max, track_seeds=selected_song_ids, track_count=track_count, seed_genre=genre
            )

            genre = genres[0]
            track_data.extend((track_id, genre) for track_id in found_tracks)
            all_seeds.extend(selected_song_ids)

            if not track_data:
                return {
                    "status": "error",
                    "message": "No tracks found matching the given criteria. Playlist generation failed."
                }
            elif len(track_data) < track_count:
                missing_tracks = track_count - len(track_data)
                random.shuffle(track_data)
                combined_seeds = ";".join(all_seeds)
                self.create_playlist(access_token, playlist_name, track_data, combined_seeds, playlist_description, genres)
                return {
                    "status": "warning",
                    "message": f"Playlista posiada mniej utworów niż zostało wpisane. Brakuje {missing_tracks} utworów, "
                               f"w celu polepszenia algorytmu spróbuj ponownie wygenerować playlistę,"
                               f"zmienić parametry systemu, bądź dodać kilka utworów do polubionych.",
                    "track_count": len(track_data)
                }
            else:
                combined_seeds = ";".join(all_seeds)
                self.create_playlist(access_token, playlist_name, track_data, combined_seeds, playlist_description, genres)
                return {
                    "status": "success",
                    "message": "Udało się stworzyć playlistę!",
                    "track_count": len(track_data)
                }

        else:
            for genre, percentage in zip(genres, genre_percentages):
                genre_track_count = max(1, round(track_count * (percentage / 100)))

                recent_songs_from_playlist_with_genre = self.db_connector.get_recent_tracks_by_genre(user, genre, limit=5)
                recent_songs = [song.spotify_id for song in recent_songs_from_playlist_with_genre]

                genre_id = Genre.objects.get(genre=genre).genre_id
                songs_filtered_by_genre = [song for song in recent_songs_from_playlist_with_genre if
                                           song.genre_id == genre_id]

                recent_playlists = self.db_connector.get_recent_playlists_by_genre(user, genre, limit=5)

                recently_added_tracks = self.get_recently_added_tracks(access_token)
                track_seeds = []

                if songs_filtered_by_genre:
                    liked_songs = list(
                        LikedSongs.objects.filter(user=user, song__genre__genre=genre).values_list('song__spotify_id',
                                                                                                   flat=True))
                    recently_added_tracks = self.get_recently_added_tracks_that_match_genre(access_token, genre,
                                                                                            recently_added_tracks)
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
                            for playlist in recent_playlists:
                                playlist_seed = playlist.seed
                                recently_added_tracks = [song for song in recently_added_tracks if
                                                         song not in playlist_seed]
                            if len(recently_added_tracks) > 0:
                                seed_track = random.choice(recently_added_tracks)
                                track_seeds = [seed_track]
                            else:
                                seed_track = random.choice([song.spotify_id for song in songs_filtered_by_genre])
                                track_seeds = [seed_track]

                    elif recently_added_tracks:
                        for playlist in recent_playlists:
                            playlist_seed = playlist.seed
                            for song in recently_added_tracks[:]:
                                if song in playlist_seed:
                                    recently_added_tracks.remove(song)

                        if len(recently_added_tracks) > 0:
                            seed_track = random.choice(recently_added_tracks)
                            track_seeds = [seed_track]

                        else:
                            seed_track = random.choice([song.spotify_id for song in songs_filtered_by_genre])
                            track_seeds = [seed_track]
                    elif len(songs_filtered_by_genre) > 0:
                        seed_track = random.choice([song.spotify_id for song in songs_filtered_by_genre])
                        track_seeds = [seed_track]


                    seed_genre = None
                else:
                    track_seeds = []
                    seed_genre = genre

                current_seed = f"{','.join(track_seeds)}" if track_seeds else seed_genre
                all_seeds.append(current_seed)

                genre_track_ids = self.search_tracks_by_features_v3(
                    access_token, target_energy, target_valence, target_tempo, target_loudness, target_danceability,
                    length_min, length_max, track_seeds, genre_track_count, seed_genre
                )

                track_data.extend((track_id, genre) for track_id in genre_track_ids)

            if not track_data:
                return {
                    "status": "error",
                    "message": "No tracks found matching the given criteria. Playlist generation failed."
                }

            if len(track_data) > track_count:
                track_data = random.sample(track_data, track_count)

            elif len(track_data) < track_count:
                missing_tracks = track_count - len(track_data)
                random.shuffle(track_data)
                combined_seeds = ";".join(all_seeds)
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

            self.create_playlist(access_token, playlist_name, track_data, combined_seeds, playlist_description, genres)
            return {
                "status": "success",
                "message": "Udało się stworzyć playlistę!",
                "track_count": len(track_data)
            }

    def get_search_results(self, access_token, query):
        url = "https://api.spotify.com/v1/search"
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        params = {
            'q': query,
            'limit': 15,
            'type': 'track'
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return []

        search_results = response.json().get('tracks', {}).get('items', [])

        tracks_data = []
        for item in search_results:
            track_info = {
                'name': item['name'],
                'artist': ", ".join(artist['name'] for artist in item['artists']),
                'spotify_id': item['id'],
                'image_url': item['album']['images'][0]['url'] if item['album']['images'] else None
            }
            tracks_data.append(track_info)

        return tracks_data

    def search_artists(self, access_token, artist_name, limit=10, offset=0):
        url = "https://api.spotify.com/v1/search"
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {
            'q': f'artist:{artist_name}',
            'type': 'artist',
            'limit': limit,
            'offset': offset
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            artists = response.json().get('artists', {}).get('items', [])
            return [
                {
                    'name': artist['name'],
                    'id': artist['id'],
                    'image_url': artist['images'][0]['url'] if artist.get('images') else None
                }
                for artist in artists
            ]
        else:
            return []

    def get_top_tracks_by_artist(self, access_token, artist_name, track_count):
        search_url = "https://api.spotify.com/v1/search"
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {
            'q': f'artist:{artist_name}',
            'type': 'artist',
            'limit': 1
        }

        artist_response = requests.get(search_url, headers=headers, params=params)
        if artist_response.status_code != 200 or not artist_response.json().get('artists', {}).get('items'):
            return []

        artist_id = artist_response.json()['artists']['items'][0]['id']

        top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
        params = {
            'market': 'EN',
            'limit': 50
        }
        top_tracks_response = requests.get(top_tracks_url, headers=headers, params=params)

        if top_tracks_response.status_code != 200:
            return []

        top_tracks = top_tracks_response.json().get('tracks', [])
        if not top_tracks:
            return []

        random.shuffle(top_tracks)
        selected_tracks = top_tracks[:track_count]

        track_list = [{
            'name': track['name'],
            'id': track['id'],
            'artist': artist_name
        } for track in selected_tracks]

        return track_list

    def create_playlist_from_tracks(self, access_token, user_id, playlist_name, track_ids):
        create_playlist_url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        playlist_data = {
            'name': playlist_name,
            'public': False
        }

        response = requests.post(create_playlist_url, headers=headers, json=playlist_data)
        if response.status_code != 201:
            return None

        playlist_id = response.json()['id']

        add_tracks_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        track_uris = [f"spotify:track:{track_id}" for track_id in track_ids]
        add_tracks_response = requests.post(add_tracks_url, headers=headers, json={'uris': track_uris})

        if add_tracks_response.status_code != 201:
            return None

        db_connector = DatabaseConnector()
        user = db_connector.get_user_by_spotify_id(user_id)
        if not user:
            return None

        playlist = db_connector.save_playlist_to_db(playlist_name, user, seeds="tastedive")
        playlist.spotify_id = playlist_id
        playlist.save()

        for track_id in track_ids:
            track_info = self.get_track_info(access_token, track_id)
            if not track_info:
                continue

            song = db_connector.save_song_to_db(track_info,
                                                genre_name="unknown")
            if not song:
                continue

            for artist_data in track_info['artists']:
                artist = db_connector.save_artist_to_db(artist_data)
                db_connector.save_song_artist_relation(song, artist)

            db_connector.save_song_playlist_relation(playlist, song)

        return response.json()
