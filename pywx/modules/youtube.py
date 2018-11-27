from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.tools import argparser
from twitch import TwitchClient
import urlparse
import datetime
from .base import ParserCommand
from registry import register_parser


hms = lambda s: ''.join(['%s%s' % (n,l) for n,l in filter(lambda x: bool(x[0]), [(s/60/60, 'h'), (s/60%60, 'm'), (s%60%60, 's')])])

def pretty_iso_duration(iso_duration):
    dd = {}
    num = 0
    timesplit = False
    duration = []
    iso_tags = (('Y', 'year'), ('M', 'month'), ('W', 'week'), ('D', 'day'))

    for s in iso_duration:
        if s.isdigit():
            num = num*10 + int(s)
            continue
        if s == 'P':
            continue
        if s == 'T':
            timesplit = True
            continue
        if timesplit and s == 'M':
            s = 'MM'
        dd[s] = num
        num = 0

    for tag, name in iso_tags:
        if tag in dd and dd[tag]:
            duration.append('%s %s%s ' % (dd[tag], name, 's' if dd[tag] > 1 else ''))
    if 'H' in dd: duration.append('%s:' % dd['H'])
    duration.append('%02d:%02d' % (dd.get('MM', 0), dd.get('S', 0)))
    duration = ''.join(duration)
    return duration

@register_parser
class YoutubeParser(ParserCommand):
    def parse(self, msg):
        lines = []
        for word in msg['msg'].split():
            vid = None
            try:
                url = urlparse.urlparse(word)
                if 'youtube' in url.netloc:
                    qs = urlparse.parse_qs(url.query)
                    vid = qs.get('v')[0] if 'v' in qs else None
                    if not vid:
                        split = url.path.split('/')
                        if split[1] == 'v':
                            vid = split[2]
                if 'youtu.be' == url.netloc:
                    vid = url.path.strip('/')
            except:
                continue

            if not vid:
                continue

            youtube = build("youtube", "v3", developerKey=self.config['youtube_key'])
            video_response = youtube.videos().list(id=vid, part='snippet, contentDetails').execute()
            video = video_response.get('items')
            if video:
                video = video[0]
            else:
                continue

            title = video["snippet"]["title"]
            duration = pretty_iso_duration(video['contentDetails']['duration'])
            lines.append("YOUTUBE: %s [%s]" % (title, duration))
        return lines

@register_parser
class TwitchParser(ParserCommand):
    def parse(self, msg):
        lines = []
        for word in msg['msg'].split():
            username = None
            try:
                url = urlparse.urlparse(word)
                if 'twitch.tv' in url.netloc:
                    username = url.path.split('/')[1]
            except:
                continue

            if not username:
                continue

            try:
                client = TwitchClient(client_id=self.config['twitch_client'], oauth_token=self.config['twitch_secret'])
                userid = client.users.translate_usernames_to_ids([username])[0]['id']
                livestreams = client.streams.get_live_streams([userid,])
                if len(livestreams):
                    ls = livestreams[0]
                    ago = (datetime.datetime.now() - ls['created_at']).seconds / 1000
                    lines.append("TWITCH: {} is LIVE, playing {} with {} viewers (started {} ago)".format(username, ls['game'], ls['viewers'], hms(ago)))
            except:
                continue

        return lines
