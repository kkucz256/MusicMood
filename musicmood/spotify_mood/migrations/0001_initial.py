# Generated by Django 5.0.7 on 2024-08-04 07:10

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Artist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('artist', models.CharField(max_length=45)),
            ],
            options={
                'db_table': 'artist',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Genre',
            fields=[
                ('genre_id', models.AutoField(primary_key=True, serialize=False)),
                ('genre', models.CharField(max_length=45)),
            ],
            options={
                'db_table': 'genre',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Language',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(max_length=45)),
            ],
            options={
                'db_table': 'language',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Playlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=45)),
                ('photo', models.TextField()),
                ('created_at', models.DateTimeField()),
            ],
            options={
                'db_table': 'playlist',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='PreferredArtist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'db_table': 'preferred artist',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='PreferredGenre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'db_table': 'preferred genre',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Settings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('song_time', models.CharField(blank=True, max_length=45, null=True)),
                ('dates', models.CharField(blank=True, max_length=45, null=True)),
            ],
            options={
                'db_table': 'settings',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Song',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('spotify_id', models.IntegerField(unique=True)),
                ('title', models.CharField(max_length=45)),
                ('duration', models.CharField(max_length=45)),
            ],
            options={
                'db_table': 'song',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='SongArtists',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'db_table': 'song_artists',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='SongsPlaylist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'db_table': 'songs_playlist',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=45)),
                ('surname', models.CharField(max_length=45)),
                ('token', models.CharField(max_length=255)),
            ],
            options={
                'db_table': 'user',
                'managed': False,
            },
        ),
    ]