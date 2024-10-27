# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Artist(models.Model):
    spotify_artist_id = models.CharField(max_length=45)
    artist = models.CharField(max_length=45)

    class Meta:
        managed = False
        db_table = 'artist'


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class Genre(models.Model):
    genre_id = models.AutoField(primary_key=True)
    genre = models.CharField(max_length=45)

    class Meta:
        managed = False
        db_table = 'genre'


class Language(models.Model):
    language = models.CharField(max_length=45)

    class Meta:
        managed = False
        db_table = 'language'


class LikedSongs(models.Model):
    user = models.ForeignKey('User', models.DO_NOTHING)
    song = models.ForeignKey('Song', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'liked_songs'


class Playlist(models.Model):
    user = models.ForeignKey('User', models.DO_NOTHING)
    name = models.CharField(max_length=45)
    photo = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    spotify_id = models.CharField(max_length=45)
    seed = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'playlist'


class PlaylistGenre(models.Model):
    playlist = models.ForeignKey(Playlist, models.DO_NOTHING)
    genre = models.ForeignKey(Genre, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'playlist_genre'


class PreferredArtist(models.Model):
    settings = models.ForeignKey('Settings', models.DO_NOTHING)
    artist = models.ForeignKey(Artist, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'preferred artist'


class PreferredGenre(models.Model):
    settings = models.ForeignKey('Settings', models.DO_NOTHING)
    genre = models.ForeignKey(Genre, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'preferred genre'


class Settings(models.Model):
    user = models.OneToOneField('User', models.DO_NOTHING)
    song_time = models.CharField(max_length=45, blank=True, null=True)
    dates = models.CharField(max_length=45, blank=True, null=True)
    language = models.OneToOneField(Language, models.DO_NOTHING, blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'settings'


class Song(models.Model):
    spotify_id = models.CharField(unique=True, max_length=45)
    title = models.CharField(max_length=100)
    duration = models.IntegerField()
    genre = models.ForeignKey(Genre, models.DO_NOTHING)
    photo_url = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'song'


class SongArtists(models.Model):
    artist = models.ForeignKey(Artist, models.DO_NOTHING)
    song = models.ForeignKey(Song, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'song_artists'


class SongsPlaylist(models.Model):
    playlist = models.ForeignKey(Playlist, models.DO_NOTHING)
    song = models.ForeignKey(Song, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'songs_playlist'


class User(models.Model):
    spotify_id = models.CharField(max_length=55)
    name = models.CharField(max_length=45)
    token = models.CharField(max_length=512)
    created_at = models.DateTimeField()
    last_login = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'user'
