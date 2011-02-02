#! /usr/bin/env python
import http.client
import os
import os.path
import pylast
import re
import sys
import time

class Live365Scrobbler():
    def __init__(self):
        # check if configuration file exists
        home = os.getenv('HOME')
        xdg_config_home = os.getenv('XDG_CONFIG_HOME', home + '/.config')
        config_file = xdg_config_home + '/live365-scrobbler/configuration'
        if not os.path.exists(config_file):
            print('No configuration found! You must specify it in this file: ' +
                  config_file)
            exit(1)
        # read configuration
        lastfm_data = dict()
        for line in open(config_file):
            line = line.strip()
            line = re.split('\s*=\s*', line)
            lastfm_data[line[0]] = line[1]
        # connect to Last.FM
        self.network = pylast.LastFMNetwork(lastfm_data['API_KEY'],
                                       lastfm_data['API_SECRET'], None,
                                       lastfm_data['USERNAME'],
                                       pylast.md5(lastfm_data['PASSWORD']))
        # connect to www.live365.com
        self.connection = http.client.HTTPConnection('www.live365.com')

    def start(self, station):
        while True:
            # get information from live365 about current track
            self.connection.connect()
            self.connection.request('GET', '/pls/front'
                                    '?handler=playlist'
                                    '&cmd=view'
                                    '&handle={}'.format(station))
            response = self.connection.getresponse()
            response = response.read()
            response = response.decode()
            track = parse_live365_playlist(response)
            # until scrobble is ready, update "now playing"
            MINIMUM_4_MINUTES = 240
            print('Now playing... {} - {}'.format(track[0], track[1]))
            sleeptime = min(MINIMUM_4_MINUTES, track[3])
            remaining = sleeptime
            while remaining:
                self.network.update_now_playing(track[0], track[1])
                updatetime = min(30, remaining)
                time.sleep(updatetime)
                remaining -= updatetime
            # scrobble and wait remaining time
            self.network.scrobble(track[0], track[1], int(track[2]))
            print('Scrobbling... {} - {}'.format(track[0], track[1]))
            if sleeptime == 240:
                time.sleep(track[3] - 240)
            # wait another time to let the song switch for sure
            time.sleep(10)


def parse_live365_playlist(html):
    def parse_javascript(regexp, splitter, data):
        var = re.search(regexp, data)
        var = var.group()
        var = var.split(splitter)[-1]
        return eval(var)
    # first, cut out the relevant buffer
    playlist = re.search(r'var playlist = {(.|\n)+?};', html)
    playlist = playlist.group()
    for item in playlist.split('},'):
        # check it it's not an ad
        if parse_javascript(r'trackType:".+?"', ':', item) == 'ad':
            continue
        # read needed info from html
        seconds_left = parse_javascript(r'gSecondsLeft\s*=\s*[0-9]+', '=', html)
        title = parse_javascript(r'title:".+?"', ':', item)
        artist = parse_javascript(r'artist:".+?"', ':', item)
        duration = parse_javascript(r'time:".+?"', 'time:', item)
        # calculate timestamp
        split = duration.split(':')
        duration = int(split[0]) * 60 + int(split[1])
        timestamp = time.time() - (duration - seconds_left)
        return artist, title, timestamp, seconds_left

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: ./live365scrobbler.py <STATION_NAME>')
        exit(1)
    scrobbler = Live365Scrobbler()
    scrobbler.start(sys.argv[1])
