from asyncio import Queue
import discord
import spotipy
from spotipy import SpotifyClientCredentials
from pytube import Search
from pytube import YouTube
from pytube import Playlist
from dotenv import load_dotenv
import os

load_dotenv()
bot = discord.Bot()

download_queue = Queue(maxsize=0)
spotify_api = None


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


"""
Joins the current channel the user is in
"""


@bot.slash_command()
async def join(ctx):
    channel = ctx.author.voice.channel
    await channel.connect()
    await ctx.respond(f'Joined Channel: {channel}')
    print(f'Joined channel: {channel}')


"""
This function adds songs to the download queue
"""


@bot.slash_command()
async def play(ctx, url):
    if url is not None:
        await parse_url(url)

    await ctx.respond(f'{url} added to the playlist')


async def parse_url(url):
    if "youtube" in url:
        await parse_youtube(url)
    elif "spotify" in url:
        await parse_spotify(url)


async def parse_youtube(url):
    if "playlist" in url:
        playlist = Playlist(url)
        await add_list_to_download_queue(playlist)
    else:
        await add_single_to_download_queue(YouTube(url))


async def parse_spotify(url):
    setup_spotify()
    if "album" in url:
        print(f'Starting to parse Spotify Album.')
        response = spotify_api.album_tracks(album_id=url)["items"]
        for song in response:
            youtube_object = convert_to_youtube(song['name'] + " by " + song['artists'][0]['name'])
            await add_single_to_download_queue(youtube_object)
        print(f'Spotify Album Parsed.')
    elif "playlist" in url:
        print(f'Starting to parse Spotify Playlist.')
        response = spotify_api.playlist_items(playlist_id=url, fields="items")["items"]
        for item in response:
            song = item['track']
            youtube_object = convert_to_youtube(song['name'] + " by " + song['artists'][0]['name'])
            await add_single_to_download_queue(youtube_object)
        print(f'Spotify Playlist Parsed.')
    elif "track" in url:
        print(f'Starting to parse Spotify Track.')
        song = spotify_api.track(track_id=url)
        youtube_object = convert_to_youtube(song['name'] + " by " + song['artists'][0]['name'])
        await add_single_to_download_queue(youtube_object)


def convert_to_youtube(song_name):
    s = Search(song_name)
    return s.results[0]


def setup_spotify():
    global spotify_api
    if spotify_api is None:
        spotify_client_id = os.getenv("SPOTIFY_API_KEY")
        spotify_client_secret = os.getenv("SPOTIFY_API_SECRET")
        spotify_api = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials(client_id=spotify_client_id,
                                                                client_secret=spotify_client_secret))


async def add_single_to_download_queue(youtube_object):
    global download_queue
    if youtube_object is not None:
        await download_queue.put(youtube_object)
        print(f'Added song to download queue: {youtube_object}')
        return
    print(f'Song was Null, Song: {youtube_object}')


async def add_list_to_download_queue(list_of_youtube):
    global download_queue
    [await download_queue.put(YouTube(youtube_object)) for youtube_object in list_of_youtube]


bot.run(os.getenv("DISCORD_API_KEY"))
