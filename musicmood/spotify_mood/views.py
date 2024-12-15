import random

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from functools import wraps
from urllib.parse import urlencode
from django.utils import timezone
from .models import User, PreferredGenre, Settings, Playlist, SongsPlaylist, SongArtists, Song, LikedSongs
from .models import Genre
from django.http import JsonResponse
from requests.exceptions import HTTPError
import json
import requests
import urllib.parse
from .classes.SpotifyAPI import SpotifyAPI


def check_access_token_expired(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            response = view_func(request, *args, **kwargs)
            if isinstance(response, JsonResponse) and response.status_code == 401:
                request.session.flush()
                params = urlencode({'message': 'Token expired'})
                url = f"{reverse('spotify_mood:show_login_page')}?{params}"
                return redirect(url)
            return response
        except HTTPError as e:
            if e.response.status_code == 401:
                request.session.flush()
                params = urlencode({'message': 'Token expired.'})
                url = f"{reverse('spotify_mood:show_login_page')}?{params}"
                return redirect(url)
            raise e

    return _wrapped_view


@check_access_token_expired
def log_in_view(request):
    spotify_api = SpotifyAPI()
    code_verifier = spotify_api.generate_code_verifier()
    request.session['code_verifier'] = code_verifier
    code_challenge = spotify_api.generate_code_challenge(code_verifier)

    auth_redirect_url = spotify_api.get_authorization_url(code_challenge)
    return redirect(auth_redirect_url)


def log_out_view(request):
    request.session.flush()
    return render(request, "spotify_mood/login.html")


def callback_view(request):
    spotify_api = SpotifyAPI()
    code = request.GET.get('code')
    code_verifier = request.session.get('code_verifier')

    if 'error' in request.GET and request.GET['error'] == 'access_denied':
        return redirect(reverse('spotify_mood:show_login_page') + '?error=access_denied')

    if not code:
        return HttpResponse("Authorization failed", status=400)

    token_info = spotify_api.get_token(code, code_verifier)

    if 'access_token' not in token_info:
        return HttpResponse("Failed to retrieve access token", status=400)

    access_token = token_info.get('access_token')
    request.session['access_token'] = access_token

    user_info = spotify_api.get_user_info(access_token)

    if 'id' not in user_info:
        return HttpResponse("Failed to retrieve user info", status=400)

    spotify_id = user_info.get('id')
    spotify_name = user_info.get('display_name', '')
    current_time = timezone.now()

    try:
        user, created = User.objects.get_or_create(
            spotify_id=spotify_id,
            defaults={
                'name': spotify_name,
                'token': access_token,
                'created_at': current_time,
                'last_login': current_time
            }
        )
        if not created:
            user.token = access_token
            user.last_login = current_time
            user.save()

    except Exception as e:
        return HttpResponse("Database error during user retrieval or update", status=500)

    request.session['user_id'] = user.id
    return redirect(reverse('spotify_mood:home'))



def show_login_page(request):
    message = request.GET.get('message', '')
    return render(request, "spotify_mood/login.html", {'message': message})


def search_genres(request):
    query = request.GET.get('q', '')
    if query:
        genres = Genre.objects.filter(genre__icontains=query).values_list('genre', flat=True)
    else:
        genres = []

    return JsonResponse({'genres': list(genres)})


@check_access_token_expired
def home_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect(reverse('spotify_mood:show_login_page'))

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('spotify_mood:show_login_page')

    user = User.objects.get(id=user_id)
    moods = ["szczęśliwy", "smutny", "spokojny", "własny"]

    mood_map = {
        '2_szczęśliwy': 1,
        '1_szczęśliwy': 0.8,
        '0_szczęśliwy': 0.733,
        '2_smutny': 0,
        '1_smutny': 0.2,
        '0_smutny': 0.266,
        '2_spokojny': 0.666,
        '1_spokojny': 0.5,
        '0_spokojny': 0.333,
        'własny': None
    }

    settings = Settings.objects.filter(user=user).first()
    preferred_genre = PreferredGenre.objects.filter(settings=settings).first()
    preferred_genre_name = preferred_genre.genre.genre if preferred_genre else ''

    if request.method == "POST":
        mood = request.POST.get('mood')
        mood_intensity = request.POST.get('intensity')
        length_choice = request.POST.get('length')
        tolerance_choice = request.POST.get('tolerance')
        selected_song_ids = None
        selected_songs_json = request.POST.get('selected_songs', '[]')

        if selected_songs_json:
            selected_songs = json.loads(selected_songs_json)
            print(selected_songs)

            selected_song_ids = [song['spotify_id'] for song in selected_songs]
            print("Selected song IDs as list:", selected_song_ids)

        genres = request.POST.get('selected_genres').split(',')
        genre_percentages = list(map(int, request.POST.get('genre_percentages').split(',')))
        print(genres, genre_percentages)
        playlist_name = request.POST.get('playlist_name', 'Moja playlista')
        playlist_description = request.POST.get('playlist_description', '')
        track_count = int(request.POST.get('track_count', 10))

        if not tolerance_choice == 0:
            length_min = int(length_choice[1]) * (100 - int(tolerance_choice)) / 100
            length_max = int(length_choice[3]) * (100 + int(tolerance_choice)) / 100
            print(length_min, length_max)
        else:
            length_min, length_max = eval(length_choice)

        mood_key = f"{mood_intensity}_{mood}" if mood != "własny" else "własny"
        mood_value = mood_map.get(mood_key)

        if mood_value is None and mood != 'własny':
            return HttpResponse(f"Nieprawidłowy nastrój {mood_key} {mood} {mood_value}", status=400)

        if mood == 'własny':
            custom_params = {
                'energy': float(request.POST.get('energy')),
                'tempo': float(request.POST.get('tempo')),
                'valence': float(request.POST.get('positivity')),
                'loudness': float(request.POST.get('loudness')),
                'danceability': float(request.POST.get('danceability')),
            }
        else:
            custom_params = None

        spotify_api = SpotifyAPI()
        if not spotify_api.is_user_logged_in(access_token):
            params = urlencode({'message': 'Token expired'})
            url = f"{reverse('spotify_mood:show_login_page')}?{params}"
            return redirect(url)

        message = spotify_api.generate_playlist_v3(
            access_token,
            mood_value,
            length_min,
            length_max,
            genres,
            genre_percentages,
            playlist_name,
            playlist_description,
            track_count,
            custom_params,
            selected_song_ids
        )
        request.session['status'] = message["status"]
        request.session['message'] = message["message"]

        cache_key = f"user_playlists_{user_id}"
        cache.delete(cache_key)
        return redirect(reverse('spotify_mood:play'))

    return render(request, "spotify_mood/home.html", {
        'user': user,
        'moods': moods,
        'preferred_genre': preferred_genre_name,
        'settings': settings,
    })


@check_access_token_expired
def settings_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect(reverse('spotify_mood:show_login_page'))

    user = get_object_or_404(User, id=user_id)
    playlists = Playlist.objects.order_by('-created_at')
    if request.method == "POST":
        song_time = request.POST.get('song_time')
        genre_preference = request.POST.get('genre_preference')

        settings, created = Settings.objects.get_or_create(user=user)

        settings.song_time = song_time
        settings.last_updated = timezone.now()
        settings.save()

        PreferredGenre.objects.filter(settings=settings).delete()

        if genre_preference:
            genre = Genre.objects.get(genre=genre_preference)
            PreferredGenre.objects.create(settings=settings, genre=genre)

        return redirect('spotify_mood:home')

    settings = Settings.objects.filter(user=user).first()
    preferred_genre = PreferredGenre.objects.filter(settings=settings).first()

    preferred_genre_name = preferred_genre.genre.genre if preferred_genre else ''

    return render(request, 'spotify_mood/settings.html', {
        'user': user,
        'settings': settings,
        'preferred_genre': preferred_genre_name,
        'playlists': playlists,
    })


@check_access_token_expired
def play_view(request):

    user_id = request.session.get('user_id')
    if not user_id:
        return redirect(reverse('spotify_mood:show_login_page'))

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect(reverse('spotify_mood:show_login_page'))

    status = request.session.pop('status', None)
    message = request.session.pop('message', None)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect(reverse('spotify_mood:show_login_page'))

    playlists_in_db = Playlist.objects.filter(user=user).order_by('-created_at')

    spotify_api = SpotifyAPI()
    spotify_playlists = spotify_api.get_user_playlists(access_token)
    if spotify_playlists is None:
        return render(request, 'spotify_mood/play.html', {
            'user': user,
            'playlist_data': [],
            'status': "error",
            'message': "Nie udało się pobrać playlist ze Spotify. Upewnij się, że jesteś zalogowany."
        })

    if not spotify_api.is_user_logged_in(access_token):
        params = urlencode({'message': 'Token expired'})
        url = f"{reverse('spotify_mood:show_login_page')}?{params}"
        return redirect(url)

    liked_songs_set = set(LikedSongs.objects.filter(user=user).values_list('song_id', flat=True))

    liked_songs_data = []
    liked_songs = LikedSongs.objects.filter(user=user).select_related('song')
    for liked_song in liked_songs:
        song = liked_song.song
        artist_relations = SongArtists.objects.filter(song=song)
        artists = [artist_relation.artist for artist_relation in artist_relations]
        track_image = song.photo_url
        liked_songs_data.append({
            'song': song,
            'artists': artists,
            'image_url': track_image,
            'liked': True
        })

    print(f"[DEBUG] Liczba polubionych utworów z danymi: {len(liked_songs_data)}")

    playlist_data = [{
        'playlist': {'name': 'Polubione utwory', 'spotify_id': None},
        'songs': liked_songs_data,
        'image_url': None
    }]

    valid_playlists = []
    for playlist in playlists_in_db:

        matched_spotify_playlist = None
        for spotify_playlist in spotify_playlists:
            if spotify_playlist is None:
                continue

            if 'id' not in spotify_playlist:
                continue

            if playlist.spotify_id == spotify_playlist['id']:
                matched_spotify_playlist = spotify_playlist
                break

        if not matched_spotify_playlist:
            continue

        songs_relations = SongsPlaylist.objects.filter(playlist=playlist)
        songs = []
        for relation in songs_relations:
            song = relation.song
            artist_relations = SongArtists.objects.filter(song=song)
            artists = [artist_relation.artist for artist_relation in artist_relations]
            track_image = song.photo_url
            is_liked = song.id in liked_songs_set

            songs.append({
                'song': song,
                'artists': artists,
                'image_url': track_image,
                'liked': is_liked
            })


        image_url = matched_spotify_playlist['images'][0]['url'] if matched_spotify_playlist.get('images') and len(
            matched_spotify_playlist['images']) > 0 else None

        valid_playlists.append({
            'playlist': playlist,
            'songs': songs,
            'image_url': image_url
        })

    print(f"[DEBUG] Liczba poprawnych playlist do wyświetlenia: {len(valid_playlists)}")

    playlist_data.extend(valid_playlists)

    return render(request, 'spotify_mood/play.html', {
        'user': user,
        'playlist_data': playlist_data,
        'status': status,
        'message': message
    })



@check_access_token_expired
def info_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect(reverse('spotify_mood:show_login_page'))

    user = get_object_or_404(User, id=user_id)
    return render(request, "spotify_mood/info.html", {'user': user})


@check_access_token_expired
def remove_preferred_genre(request):
    user_id = request.session.get('user_id')
    genre_name = request.GET.get('genre')

    if user_id and genre_name:
        genre = Genre.objects.get(genre=genre_name)
        PreferredGenre.objects.filter(user_id=user_id, genre=genre).delete()
        return JsonResponse({'success': True})

    return JsonResponse({'success': False})


@check_access_token_expired
def search_artists(request):
    query = request.GET.get('q', '')
    access_token = request.session.get('access_token')

    if not query:
        return JsonResponse({'artists': []})

    spotify_api = SpotifyAPI()
    artists = spotify_api.search_artists_by_genre(access_token, query)

    return JsonResponse({'artists': artists})


@csrf_exempt
def like_song(request, song_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
        song = Song.objects.get(id=song_id)

        LikedSongs.objects.get_or_create(user=user, song=song)

        return JsonResponse({'status': 'liked'})

    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
def unlike_song(request, song_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
        song = Song.objects.get(id=song_id)

        LikedSongs.objects.filter(user=user, song=song).delete()

        return JsonResponse({'status': 'unliked'})

    return JsonResponse({'error': 'Invalid request'}, status=400)


def search_song_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect(reverse('spotify_mood:show_login_page'))
    access_token = request.session.get('access_token')

    if request.method == "POST":
        spotify_api = SpotifyAPI()

        if not spotify_api.is_user_logged_in(access_token):
            params = urlencode({'message': 'Token expired'})
            url = f"{reverse('spotify_mood:show_login_page')}?{params}"
            print("Redirect URL:", url)
            return JsonResponse({'redirect': url})

        song_name = request.POST.get('song_name', '')
        results = spotify_api.get_search_results(access_token, song_name)
        return JsonResponse({'songs': results})

    return JsonResponse({'error': 'Invalid request'}, status=400)

def tastedive(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect(reverse('spotify_mood:show_login_page'))

    user = User.objects.get(id=user_id)

    if request.method == "POST":
        artist_name = request.POST.get('selected_artist')
        track_count = int(request.POST.get('track_count', 10))

        try:
            artist_data = json.loads(artist_name)
        except json.JSONDecodeError:
            return render(request, "spotify_mood/tastedive.html", {'user': user, 'error': "Niepoprawny format danych artysty!"})

        if "name" not in artist_data:
            return render(request, "spotify_mood/tastedive.html", {'user': user, 'error': "Nie znaleziono klucza 'name' w danych artysty!"})

        artist_name_value = artist_data["name"]

        tastedive_api_key = "1039779-MusicMoo-346EAE01"
        encoded_artist_name = urllib.parse.quote_plus(artist_name_value)
        tastedive_url = f"https://tastedive.com/api/similar?q={encoded_artist_name}&type=music&k={tastedive_api_key}&info=0"
        response = requests.get(tastedive_url)
        print(f"TasteDive URL: {tastedive_url}")

        if response.status_code != 200:
            print("Błąd z API TasteDive!")
            return render(request, "spotify_mood/tastedive.html", {'user': user, 'error': "Błąd z API TasteDive!"})

        data = response.json()
        similar_artists = [
                              result.get('name') for result in data.get('similar', {}).get('results', [])
                              if result.get('type') == 'music'
                          ][:10]

        if not similar_artists:
            return render(request, "spotify_mood/tastedive.html", {'user': user, 'error': "Nie znaleziono podobnych artystów."})

        for artist in similar_artists:
            print(f"- {artist}")

        spotify_api = SpotifyAPI()
        access_token = request.session.get('access_token')

        songs_per_artist = max(1, track_count // 10)
        all_track_ids = []

        for artist in similar_artists:
            tracks = spotify_api.get_top_tracks_by_artist(access_token, artist, songs_per_artist)
            for track in tracks:
                all_track_ids.append(track['id'])

        random.shuffle(all_track_ids)
        playlist_name = request.POST.get('playlist_name', f"Playlista na podstawie {artist_name_value}")

        spotify_api.create_playlist_from_tracks(
            access_token=access_token,
            user_id=user.spotify_id,
            playlist_name=playlist_name,
            track_ids=all_track_ids
        )

        return redirect(reverse('spotify_mood:play'))

    return render(request, "spotify_mood/tastedive.html", {'user': user})

@check_access_token_expired
def search_artist_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'User not authenticated'}, status=401)

    access_token = request.session.get('access_token')
    artist_name = request.GET.get('q', '').strip()

    if not artist_name:
        return JsonResponse({'error': 'Artist name is required'}, status=400)

    spotify_api = SpotifyAPI()
    results = spotify_api.search_artists(access_token, artist_name)

    return JsonResponse({'artists': results})