#!/usr/bin/env python3

"""
Author - Kostya Belykh k@belykh.su
Language - Python 3.6+
This script is designed to sync your music libraries between Spotify and 
 Yandex music using Spotify as source of your library and Ya.Music as 
 destination. This script is designed to make possible of use Yandex station
 as sound center in house with music gathered from Spotify. It will clone music 
 your 'Liked Sounds' playlist in Spotify to 'Liked songs' playlist in Ya.Music.
"""

from optparse import OptionParser
from configparser import ConfigParser
import sys
import logging
import os
import time
import random
import string
import sqlite3
import requests
from sqlite3 import Error
try:
    from yandex_music import Client
    logging.getLogger("yandex_music").setLevel(logging.ERROR)
    Client.notice_displayed = True
except ImportError:
    print("Failed to import yandex-music module.")
    print('Try "pip3 install yandex-music"')
    sys.exit(1)
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from spotipy.exceptions import SpotifyException
except ImportError:
    print("Failed to import spotipy module.")
    print('Try "pip3 install spotipy"')
    sys.exit(1)
try:
    from transliterate import translit
except ImportError:
    print("Failed to import transliterate module.")
    print('Try "pip3 install transliterate"')
    sys.exit(1)

start = time.time()
logger = logging.getLogger()
randomseed = result_str = "".join(
    (random.choice(string.ascii_letters) for i in range(10))
)


def parseCommandOptions():

    # Parsing input parameters
    p = OptionParser(add_help_option=False, usage="%prog [options]")
    p.add_option(
        "--help",
        action="store_true",
        dest="help",
        help="Show this message and exit."
    )
    p.add_option(
        "-c",
        "--config",
        dest="config",
        help="Configuration file. " + "If not passed - uses ./config.conf",
        default=os.path.dirname(os.path.realpath(__file__)) + "/config.conf",
    )
    p.add_option(
        "-s",
        "--section",
        dest="section",
        help="Configuration section. If not passed "
        + "- [spotify-to-yandex-music-exporter] used.",
        default="spotify-to-yandex-music-exporter",
    )
    (options, args) = p.parse_args()

    if options.help:
        p.print_help()
        exit()

    parser = ConfigParser()
    configfile = options.section
    parser.read(options.config)

    spotifyclientid = parser.get(configfile, "spotifyclientid")
    spotifyclientsecret = parser.get(configfile, "spotifyclientsecret")
    yandexmusiclogin = parser.get(configfile, "yandexmusiclogin")
    yandexmusicpassword = parser.get(configfile, "yandexmusicpassword")
    loggingenabled = parser.getboolean(configfile, "loggingenabled")

    # Setup logging
    if loggingenabled:
        loglevel = parser.get(configfile, "logginglevel")
        logfile = parser.getboolean(configfile, "loggingfile")
        logconsole = parser.getboolean(configfile, "loggingconsole")
        logpath = parser.get(configfile, "loggingfilepath")
        logFormatStr = "%(asctime)s - %(levelname)-8s - %(message)s"

        logger.setLevel(loglevel)
        formatter = logging.Formatter(logFormatStr)
        if logconsole:
            chandler = logging.StreamHandler()
            chandler.setFormatter(formatter)
            logger.addHandler(chandler)
        if logfile:
            fhandler = logging.FileHandler(filename=logpath)
            fhandler.setFormatter(formatter)
            logger.addHandler(fhandler)

    if (
        spotifyclientid
        and spotifyclientsecret
        and yandexmusiclogin
        and yandexmusicpassword
    ):
        main(
            spotifyclientid,
            spotifyclientsecret,
            yandexmusiclogin,
            yandexmusicpassword
        )
    else:
        print("The required parameters is missing. Runtime parameters:")
        print(sys.argv[1:])
        exit()


def spotifyGetAuth(spotifyclientid, spotifyclientsecret):
    logging.info("Connecting to spotify")
    try:
        sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=spotifyclientid,
                client_secret=spotifyclientsecret,
                redirect_uri="http://localhost",
                scope="user-library-read",
                open_browser=False,
            )
        )
        return sp
    except SpotifyException as e:
        logging.error("Problem getting auth from spotify:")
        logging.error(e)
        sys.exit(1)


def spotifyGetFavoriteSongs(sp):
    logging.info("Downloading list of favorite songs from spotify")
    songs = list()
    soffset = int(0)
    slimit = int(50)
    try:
        total = int(sp.current_user_saved_tracks(limit=1)["total"])
        logging.debug("  Total number of favorite songs is {}".format(total))
    except SpotifyException as e:
        logging.error("Problem getting number of favorite songs on spotify:")
        logging.error(e)
        sys.exit(1)
    while total > 0:
        try:
            part = sp.current_user_saved_tracks(limit=slimit, offset=soffset)
            for item in part["items"]:
                songs.append(item)
            soffset += slimit
            total -= slimit
            if total > 0:
                logging.debug("  {} songs remained".format(total))
            else:
                logging.info("  Favorite songs info from spotify downloaded")
        except SpotifyException as e:
            logging.error("Problem downloading favorite songs on spotify:")
            logging.error(e)
            sys.exit(1)
    return songs


def updateDatabaseOfSongs(spotifyfavoritesongs):
    logging.info("Updating local database of songs")
    try:
        conn = sqlite3.connect(os.path.dirname(
            os.path.realpath(__file__)) + "/.songs")
        c = conn.cursor()
    except Error as e:
        logging.error("Error with connecting to sqlite base")
        logging.error(e)
        sys.exit(1)

    # creating table if it is not exitst
    try:
        c.execute(
            """SELECT count(name) 
                     FROM sqlite_master 
                     WHERE type='table' AND name='songs' 
                     """
        )
    except Error as e:
        logging.error("Error with checking existance of table in database")
        logging.error(e)
        sys.exit(1)
    if c.fetchone()[0] == 0:
        logging.warning("  Database file does not exists. Creating.")
        databasexisted = False
        try:
            c.execute(
                """CREATE TABLE songs
                         ([id] INTEGER PRIMARY KEY,
                          [spotifyid] TEXT,
                          [artist_name] TEXT,
                          [song_name] TEXT,
                          [album_name] TEXT,
                          [liked] INTEGER,
                          [song_length] INTEGER,
                          [seed] TEXT
                          )"""
            )
            conn.commit()
        except Error as e:
            logging.error("Error with creating table in database")
            logging.error(e)
            sys.exit(1)
    else:
        databasexisted = True

    # resetting 'liked' stat to track which songs we did not like anymore
    if databasexisted:
        try:
            c.execute(
                """UPDATE songs
                         SET liked = 0"""
            )
            conn.commit()
        except Error as e:
            logging.error("Error with set all songs to unliked")
            logging.error(e)
            sys.exit(1)

    # Determining per song what to do
    for song in spotifyfavoritesongs:
        artists = list()
        astr = str()
        for artist in song["track"]["artists"]:
            artists.append(artist["name"])
        for a in artists:
            astr += str(a) + ", "
        astr = astr[:-2]
        # Checking if song already in database
        c.execute(
            """SELECT count(*) 
                     FROM songs 
                     WHERE spotifyid = ?""",
            [str(song["track"]["id"])],
        )
        if c.fetchone()[0] == 0:
            logging.debug(
                '  Song "{} - {}" not in database, adding'.format(
                    astr, song["track"]["name"]
                )
            )
            songnotindb = True
        else:
            songnotindb = False
        if songnotindb:
            # Adding song to database
            try:
                c.execute(
                    """INSERT INTO songs
                              (spotifyid,
                              artist_name,
                              song_name,
                              album_name,
                              liked,
                              song_length,
                              seed)
                             VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [
                        str(song["track"]["id"]),
                        str(astr),
                        str(song["track"]["name"]),
                        str(song["track"]["album"]["name"]),
                        int(1),
                        int(song["track"]["duration_ms"]),
                        str(randomseed),
                    ],
                )
                conn.commit()
            except Error as e:
                logging.error("Error with adding song to table in database")
                logging.error(e)
                sys.exit(1)
        else:
            # Updating currently existing song
            try:
                c.execute(
                    """UPDATE songs
                             SET liked = '1'
                             WHERE spotifyid = ?""",
                    [str(song["track"]["id"])],
                )
                conn.commit()
            except Error as e:
                logging.error("Error with updating song in table")
                logging.error(e)
                sys.exit(1)
    conn.close()


def yandexMusicGetAuth(login, password):
    logging.info("Connecting to yandex music")
    # Checking if we have token file to use in auth
    # Tokens are used in case we have 2fa auth with one time passwords instead
    # of regular passwords
    if os.path.isfile(os.path.dirname(os.path.realpath(__file__)) + "/.token"):
        with open(os.path.dirname(os.path.realpath(__file__)) + "/.token",
                  "r") as f:
            token = f.read()
            f.close()
    else:
        # If we don't have token -- we need to create new one
        token = captcha_key = captcha_answer = None
        while not token:
            data = {
                'grant_type': 'password',
                # id and secret is from yandex.music application for android
                'client_id': '23cabbbdc6cd418abb4b39c32c41195d',
                'client_secret': '53bc75238f0c4d08a118e51fe9203300',
                'username': login,
                'password': password,
                'x_captcha_key': captcha_key,
                'x_captcha_answer': captcha_answer
            }
            response = requests.post('https://oauth.yandex.com/token', 
                                      data=data)
            try:
                if response.json()['access_token']:
                    token = response.json()['access_token']
            except KeyError:
                pass
            try:
                if response.json()['error_description'] == 'CAPTCHA required' or \
                    response.json()['error_description'] == 'Wrong CAPTCHA answer':
                    captcha_key = response.json()['x_captcha_key']
                    captcha_url = response.json()['x_captcha_url']
                    captcha_answer = input("Input numbers from {} : ".format(
                        captcha_url
                    ))
                if response.json()['error_description'] == 'login or password is not valid':
                    password = input('Wrong password. If you use 2FA - input it: ')
            except KeyError:
                pass
        with open(os.path.dirname(os.path.realpath(__file__)) + "/.token",
                  "w+") as f:
            f.write(token)
            f.close()
    # Authenticating ourself
    try:
        ya = Client(token)
    except Error as e:
        logging.error("Cannot connect to yandex music")
        logging.error(e)
        sys.exit(1)
    return ya


def updateYandexSongs(ya):
    def searchSong(artist, album, song, length):
        result = str()
        similarity = int()
        diffms = int(5000)

        searchresult = ya.search("{} - {}".format(artist, song))
        if searchresult["best"]:
            try:
                # checking if name of song is same
                if searchresult["best"]["result"]["title"] == song:
                    similarity += 1
                # checking if author of song is same
                for a in searchresult["best"]["result"]["artists"]:
                    if str(a["name"]).lower() in str(artist).lower():
                        similarity += 1
                    elif translit(str(a["name"]).lower(),
                                  "ru") in str(artist).lower():
                        similarity += 1
                # checking if album name is same
                for a in searchresult["best"]["result"]["albums"]:
                    if a["title"] in album:
                        similarity += 1
                # checking if length is similar
                if (
                    abs(int(searchresult["best"]["result"]
                        ["duration_ms"]) - length)
                    < diffms
                ):
                    similarity += 1
                # cheking if it is even a song
                if searchresult["best"].type != "track":
                    similarity = 0
            except KeyError:
                pass
            except TypeError:
                pass

            if similarity > 2:
                result = str(searchresult["best"]["result"].id)
        return result

    def songworker(song):
        # [0] - int id
        # [1] - str spotifyid
        # [2] - str Author(s)
        # [3] - str Name
        # [4] - str Album
        # [5] - str is liked
        # [6] - int length in ms
        # [7] - str random seed used when this song added to base
        if song[7] == randomseed and song[5] == 1:
            # add like to song
            sid = searchSong(song[2], song[4], song[3], song[6])
            if sid:
                like = ya.users_likes_tracks_add(sid)
                if like:
                    logging.debug(
                        '  Track "{} - {}" liked'.format(
                            str(song[2]), str(song[3]))
                    )
                else:
                    logging.error(
                        'Error liking "{} - {}"'.format(
                            str(song[2]), str(song[3]))
                    )
            else:
                logging.warning(
                    '  Cannot find song "{} - {}"'.format(
                        str(song[2]), str(song[3]))
                )
        if song[5] == 0:
            # remove like from song
            sid = searchSong(song[2], song[4], song[3], song[6])
            if sid:
                dislike = ya.users_likes_tracks_remove(sid)
                if dislike:
                    logging.debug(
                        '  Track "{} - {}" disliked'.format(
                            str(song[2]), str(song[3]))
                    )
                else:
                    logging.error(
                        'Error disliking "{} - {}"'.format(
                            str(song[2]), str(song[3]))
                    )
            else:
                logging.warning(
                    '  Cannot find song "{} - {}"'.format(
                        str(song[2]), str(song[3]))
                )

    logging.info("Updating yandex songs")
    try:
        conn = sqlite3.connect(os.path.dirname(
            os.path.realpath(__file__)) + "/.songs")
        c = conn.cursor()
    except Error as e:
        logging.error("Error working sqlite base")
        logging.error(e)
        sys.exit(1)
    # Fetching all data from database
    try:
        c.execute(
            """SELECT * FROM songs"""
        )
        songs = c.fetchall()
    except Error as e:
        logging.error("Error fetching songs from sqlite base")
        logging.error(e)
        sys.exit(1)

    # Reserved to preserve order of songs as seen on spotify
    for song in reversed(songs):
        # TODO: think about multithreading this work while preserving
        #  order of songs.
        songworker(song)

    conn.close()


def main(spotifyclientid,
         spotifyclientsecret,
         yandexmusiclogin,
         yandexmusicpassword):
    logging.info("***********************************************************")
    logging.info("Script started")
    logging.debug("Runtime parameters:")
    logging.debug(sys.argv[1:])

    sp = spotifyGetAuth(spotifyclientid, spotifyclientsecret)
    ya = yandexMusicGetAuth(yandexmusiclogin, yandexmusicpassword)
    spfavoritesongs = spotifyGetFavoriteSongs(sp)
    updateDatabaseOfSongs(spfavoritesongs)
    updateYandexSongs(ya)

    logging.info(
        "Script finished. Runtime: {} seconds.".format(
            str(round(time.time() - start, 3))
        )
    )


if __name__ == "__main__":
    parseCommandOptions()
