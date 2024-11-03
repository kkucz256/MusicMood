from django.urls import path
from . import views

app_name = "spotify_mood"

urlpatterns = [
    path('', views.show_login_page, name='show_login_page'),
    path('log_in/', views.log_in_view, name='log_in'),
    path('callback/', views.callback_view, name='callback'),
    path('logout/', views.log_out_view, name='logout'),
    path('home/', views.home_view, name='home'),
    path('settings/', views.settings_view, name='settings'),
    path('play/', views.play_view, name='play'),
    path('info/', views.info_view, name='info'),
    path('search_genres/', views.search_genres, name='search_genres'),
    path('search_artists/', views.search_artists, name='search_artists'),
    path('like_song/<int:song_id>/', views.like_song, name='like_song'),
    path('unlike_song/<int:song_id>/', views.unlike_song, name='unlike_song'),
    path('search_song/', views.search_song_view, name='search_song'),
]

