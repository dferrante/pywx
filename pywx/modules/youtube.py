from urllib.parse import parse_qs, urlparse

from apiclient.discovery import build

from .base import ParserCommand
from .registry import register_parser


def pretty_iso_duration(iso_duration):
    if iso_duration == 'P0D':
        return 'LIVE'

    isostring = {}
    num = 0
    timesplit = False
    duration = []
    iso_tags = (('Y', 'year'), ('M', 'month'), ('W', 'week'), ('D', 'day'))

    for char in iso_duration:
        if char.isdigit():
            num = num * 10 + int(char)
            continue
        if char == 'P':
            continue
        if char == 'T':
            timesplit = True
            continue
        if timesplit and char == 'M':
            char = 'MM'
        isostring[char] = num
        num = 0

    for tag, name in iso_tags:
        if tag in isostring and isostring[tag]:
            duration.append(f'{isostring[tag]} {name}{"s" if isostring[tag] > 1 else ""} ')
    if 'H' in isostring:
        duration.append(f'{isostring["H"]:02d}:')

    duration.append(f"{isostring.get('MM', 0):02d}:{isostring.get('S', 0):02d}")
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
                    params = parse_qs(url.query)
                    vid = params.get('v')[0] if 'v' in params else None
                    if not vid:
                        split = url.path.split('/')
                        if split[1] == 'v' or split[1] == 'shorts':
                            vid = split[2]
                if 'youtu.be' == url.netloc:
                    vid = url.path.strip('/')
            except Exception: # pylint: disable=broad-except
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
            channel = video['snippet']['channelTitle']
            duration = pretty_iso_duration(video['contentDetails']['duration'])
            lines.append(f"YOUTUBE: {title} [{duration}] [{channel}]")
        return lines
