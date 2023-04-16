from asyncio import Queue
import discord
import spotipy
from spotipy import SpotifyClientCredentials
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
        return parse_youtube(url)
    elif "spotify" in url:
        return await parse_spotify(url)


def parse_youtube(url):
    if "playlist" in url:
        print("Not Implemented")
    return None


async def parse_spotify(url):
    setup_spotify()
    if "album" in url:
        print(f'Starting to parse Spotify Album.')
        response = spotify_api.album_tracks(album_id=url)["items"]
        for song in response:
            await add_to_download_queue(song['name'] + " by " + song['artists'][0]['name'])
        print(f'Spotify Album Parsed.')
    elif "playlist" in url:
        print(f'Starting to parse Spotify Playlist.')
        response = spotify_api.playlist_items(playlist_id=url, fields="items")["items"]
        for item in response:
            song = item['track']
            await add_to_download_queue(song['name'] + " by " + song['artists'][0]['name'])
        print(f'Spotify Playlist Parsed.')
    elif "track" in url:
        print(f'Starting to parse Spotify Track.')
        song = spotify_api.track(track_id=url)
        await add_to_download_queue(song['name'] + " by " + song['artists'][0]['name'])


def setup_spotify():
    global spotify_api
    if spotify_api is None:
        spotify_client_id = os.getenv("SPOTIFY_API_KEY")
        spotify_client_secret = os.getenv("SPOTIFY_API_SECRET")
        spotify_api = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials(client_id=spotify_client_id,
                                                                client_secret=spotify_client_secret))


async def add_to_download_queue(song):
    global download_queue
    if song is not None:
        await download_queue.put(song)
        print(f'Added song to download queue: {song}')
        return
    print(f'Song was Null, Song: {song}')


bot.run(os.getenv("DISCORD_API_KEY"))
