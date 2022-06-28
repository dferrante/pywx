from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.tools import argparser
from urllib.parse import urlparse, parse_qs
from .base import ParserCommand
from .registry import register_parser


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
                url = urlparse(word)
                if 'youtube' in url.netloc:
                    qs = parse_qs(url.query)
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

