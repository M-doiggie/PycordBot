from asyncio import Queue
import discord
from discord.ext import tasks
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
play_queue = Queue(maxsize=10)
spotify_api = None


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


"""
####################
Bot Control Commands
####################
"""


@bot.slash_command()
async def join(ctx):
    """
    Joins the current channel the user is in

    Args:
        :arg1 (Context): Current Context of the bot
    """
    channel = ctx.author.voice.channel
    await channel.connect()
    start_tasks(ctx)
    await ctx.respond(f'Joined Channel: {channel}')
    print(f'Joined channel: {channel}')


@bot.slash_command()
async def leave(ctx):
    voice_client = ctx.guild.voice_client
    channel = voice_client.channel
    await voice_client.disconnect()
    await ctx.respond(f'Left Channel: {channel}')


@tasks.loop(seconds=10)
async def auto_leave(ctx):
    channel = ctx.guild.voice_client.channel
    if channel is not None:
        members = channel.members
        if len(members) == 1:
            await leave(ctx)


def start_tasks(ctx):
    """
    This function will start the tasks of the bot.

    Args:
        :arg1 (Context): The current Context of the bot
    """
    if not check_for_playing.is_running():
        check_for_playing.start(ctx)
    if not check_for_downloads.is_running():
        check_for_downloads.start()
    if not auto_leave.is_running():
        auto_leave.start(ctx)


"""
##############
Music Commands
##############
"""


@bot.slash_command()
async def play(ctx, url):
    """
    This function adds songs to the download queue

    Args:
        :arg1 (Context): Current Context of the bot
        :arg2 (String): YouTube or Spotify URL
    """
    if url is not None:
        await parse_url(url)

    await ctx.respond(f'{url} added to the playlist')


@bot.slash_command()
async def skip(ctx):
    channel = ctx.guild.voice_client
    if channel is not None:
        channel.stop()
        await ctx.respond(f'Skipped current song')

async def parse_url(url):
    """
    This function parses the url into either YouTube or Spotify Links

    Args:
        :arg1 (String): YouTube or Spotify URL
    """
    if "youtube" in url:
        await parse_youtube(url)
    elif "spotify" in url:
        await parse_spotify(url)


async def parse_youtube(url):
    """
    This function parses the YouTube url into either single video or a playlist
    and then converts to YouTube objects and adds the song to the download queue

    Args:
        :arg1 (String): YouTube URL
    """
    if "playlist" in url:
        playlist = Playlist(url)
        await add_list_to_download_queue(playlist)
    else:
        await add_single_to_download_queue(YouTube(url))


async def parse_spotify(url):
    """
    This function parses the spotify url into either single song, playlist or album
    then converts to YouTube objects and adds all songs to the download queue

    Args:
        :arg1 (String): Spotify URL
    """
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
    """
    This function converts the name of a song and searches on YouTube for all related
    requests and returns the top most result.

    Args:
        :arg1 (String): Name and artist of song

    Returns:
        YouTube: The top most result of the searched string
    """
    s = Search(song_name)
    return s.results[0]


def setup_spotify():
    """
    Sets up the spotify api to used to parse spotify links for information.
    """
    global spotify_api
    if spotify_api is None:
        spotify_client_id = os.getenv("SPOTIFY_API_KEY")
        spotify_client_secret = os.getenv("SPOTIFY_API_SECRET")
        spotify_api = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials(client_id=spotify_client_id,
                                                                client_secret=spotify_client_secret))


async def add_single_to_download_queue(youtube_object):
    """
    This function adds a single YouTube object to the download queue

    Args:
        :arg1 (YouTube): A YouTube object of the desired song
    """
    global download_queue
    if youtube_object is not None:
        await download_queue.put(youtube_object)
        print(f'Added song to download queue: {youtube_object}')
        return
    print(f'Song was Null, Song: {youtube_object}')


async def add_list_to_download_queue(list_of_youtube):
    """
    This function adds all of the YouTube objects from a list to the download queue

    Args:
        :arg1 (List<YouTube>): Spotify URL
    """
    global download_queue
    [await download_queue.put(YouTube(youtube_object)) for youtube_object in list_of_youtube]


@tasks.loop(seconds=5)
async def check_for_downloads():
    """
    This function checks the download queue every 5 seconds to see if there is a
    song which has been requested to be downloaded. If there is, then it will proceed
    to download the audio stream of the YouTube object and add the filename to the
    play queue.

    It will also start the check_for_playing task if not already started.
    """
    if not download_queue.empty() and not play_queue.full():
        song_to_download = await download_queue.get()
        try:
            audio = song_to_download.streams.get_by_itag(140)
            filename = audio.download()
            await play_queue.put(filename)
            print(f'Song Downloaded: {song_to_download.title}')
        except Exception as ex:
            print(f'An Issue came up when trying to download a song: {ex}')

        if not check_for_playing.is_running():
            check_for_playing.start()


@tasks.loop(seconds=5)
async def check_for_playing(ctx):
    """
    This function checks the play queue every 5 seconds to see if a song is ready
    to be played, then plays the song using FFmpegPCMAudio, and deletes the downloaded
    file after it has finished.

    Args:
        :arg1 (Context): The current Context of the bot
    """
    if ctx is not None:
        voice_client = ctx.voice_client
        if not play_queue.empty() and voice_client.is_connected() and not voice_client.is_playing():
            try:
                current_song = await play_queue.get()
                voice_client.play(discord.FFmpegPCMAudio(source=current_song),
                                  after=lambda e: delete_song(current_song))
                print('**Now playing:** {}'.format(current_song.split("\\")[-1]))
                await ctx.send('**Now playing:** {}'.format(current_song.split("\\")[-1]))
            except Exception as e:
                print(f'An Exception occurred when trying to play music, Exception: {e}')


def delete_song(filename):
    """
    This function will delete songs from the local machine.

    Args:
        :arg1 (String): The filepath to the desired file.
    """
    try:
        os.remove(filename)
        print(f'Successfully deleted song: {filename}')
    except OSError as ex:
        print(f'Ran into issue when deleting {filename}, caused this exception: {ex}')


bot.run(os.getenv("DISCORD_API_KEY"))
