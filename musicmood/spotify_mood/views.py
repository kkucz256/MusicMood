from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.core.cache import cache
from functools import wraps
from urllib.parse import urlencode
from django.utils import timezone
from .models import User, PreferredGenre, Settings, Playlist, SongsPlaylist, SongArtists
from .models import Genre
from django.http import JsonResponse
from requests.exceptions import HTTPError
import os
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

    if not code:
        return HttpResponse("Authorization failed", status=400)

    token_info = spotify_api.get_token(code, code_verifier)

    if 'access_token' not in token_info:
        return HttpResponse("Failed to retrieve access token", status=400)

    access_token = token_info.get('access_token')
    request.session['access_token'] = access_token

    user_info = spotify_api.get_user_info(access_token)
    spotify_id = user_info.get('id')
    spotify_name = user_info.get('display_name', '')
    current_time = timezone.now()

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
        '1_szczęśliwy': 0.75,
        '0_szczęśliwy': 0.625,
        '2_smutny': 0,
        '1_smutny': 0.25,
        '0_smutny': 0.375,
        '2_spokojny': 0.625,
        '1_spokojny': 0.5,
        '0_spokojny': 0.375,
        'własny': None
    }

    settings = Settings.objects.filter(user=user).first()
    preferred_genre = PreferredGenre.objects.filter(settings=settings).first()
    preferred_genre_name = preferred_genre.genre.genre if preferred_genre else ''

    if request.method == "POST":
        mood = request.POST.get('mood')
        mood_intensity = request.POST.get('intensity')
        length_choice = request.POST.get('length')

        genres = request.POST.get('selected_genres').split(',')
        genre_percentages = list(map(int, request.POST.get('genre_percentages').split(',')))
        print(genres, genre_percentages)
        playlist_name = request.POST.get('playlist_name', 'Moja playlista')
        playlist_description = request.POST.get('playlist_description', '')
        track_count = int(request.POST.get('track_count', 10))

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
        spotify_api.generate_playlist_v2(
            access_token,
            mood_value,
            length_min,
            length_max,
            genres,
            genre_percentages,
            playlist_name,
            playlist_description,
            track_count,
            custom_params
        )
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
    })


@check_access_token_expired
def play_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect(reverse('spotify_mood:show_login_page'))

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect(reverse('spotify_mood:show_login_page'))

    user = User.objects.get(id=user_id)

    cache_key = f"user_playlists_{user_id}"
    valid_playlists = cache.get(cache_key)

    if not valid_playlists:
        playlists_in_db = Playlist.objects.filter(user=user).order_by('-created_at')

        spotify_api = SpotifyAPI()
        spotify_playlists = spotify_api.get_user_playlists(access_token)

        valid_playlists = []
        for playlist in playlists_in_db:
            for spotify_playlist in spotify_playlists:
                if playlist.spotify_id == spotify_playlist['id']:
                    songs_relations = SongsPlaylist.objects.filter(playlist=playlist)
                    songs = []
                    for relation in songs_relations:
                        song = relation.song
                        artist_relations = SongArtists.objects.filter(song=song)
                        artists = [artist_relation.artist for artist_relation in artist_relations]

                        track_info = spotify_api.get_track_info(access_token, song.spotify_id)
                        track_image = track_info['album']['images'][0]['url'] if track_info.get('album') and track_info[
                            'album'].get('images') and len(track_info['album']['images']) > 0 else None

                        songs.append({
                            'song': song,
                            'artists': artists,
                            'image_url': track_image
                        })

                    image_url = spotify_playlist['images'][0]['url'] if spotify_playlist.get('images') and len(
                        spotify_playlist['images']) > 0 else None
                    valid_playlists.append({
                        'playlist': playlist,
                        'songs': songs,
                        'image_url': image_url
                    })

        cache.set(cache_key, valid_playlists, timeout=300)

    return render(request, 'spotify_mood/play.html', {
        'user': user,
        'playlist_data': valid_playlists
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
