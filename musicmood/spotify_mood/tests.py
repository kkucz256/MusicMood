from django.test import TestCase
import requests
from .classes.SpotifyAPI import SpotifyAPI


spotify_api = SpotifyAPI()


def get_access_token():
    print("Masz już access_token?")
    choice = input("Wpisz 'tak', aby wkleić token ręcznie, lub 'nie', aby przejść pełną autoryzację: ").lower()

    if choice == 'tak':
        access_token = input("Wklej swój access_token: ")
        return access_token
    else:
        code_verifier = spotify_api.generate_code_verifier()
        code_challenge = spotify_api.generate_code_challenge(code_verifier)

        auth_redirect_url = spotify_api.get_authorization_url(code_challenge)
        print(f"Zaloguj się i uzyskaj kod autoryzacji, wchodząc na ten URL: {auth_redirect_url}")

        auth_code = input("Wklej otrzymany kod autoryzacyjny (auth_code): ")

        token_info = spotify_api.get_token(auth_code, code_verifier)

        if 'access_token' in token_info:
            access_token = token_info['access_token']
            print("Autoryzacja zakończona pomyślnie! Access token: ", access_token)
            return access_token
        else:
            print("Nie udało się uzyskać access tokena.")
            return None



access_token = get_access_token()

if access_token:
    def check_token(access_token):
        url = "https://api.spotify.com/v1/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            print("Token is valid.")
        else:
            print(f"Token validation failed with status code: {response.status_code} - {response.text}")


    check_token(access_token)

    genres = ['hip-hop']
    genre_percentages = [70]
    artists = ['Kanye West']
    artist_percentages = [50]
    mood_value = 0.6
    min_duration = 3
    max_duration = 5

    spotify_api.generate_playlist(access_token, mood_value, min_duration, max_duration, genres, genre_percentages,
                                  artists, artist_percentages)
else:
    print("Brak access_token, nie można kontynuować.")
