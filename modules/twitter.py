import json
import subprocess
from urllib.parse import urlparse

from .base import ParserCommand, irc_color
from .registry import register_parser


@register_parser
class TwitterParser(ParserCommand):
    multiline = True

    def parse(self, msg):
        if not self.config.get("twitter_token"):
            return []

        lines = []
        for word in msg['msg'].split(' '):
            url = urlparse(word)
            if 'twitter' in url.netloc:
                path = url.path
                try:
                    username = path.split('/')[1]
                    twid = path.split('/')[3]

                    scrape = subprocess.run(['snscrape', '--jsonl', 'twitter-tweet', twid], capture_output=True, check=False)
                    if scrape.returncode != 0:
                        return []

                    tweet = json.loads(scrape.stdout)
                    text = tweet['content']
                    verified = tweet['user']['verified']

                    tweetlines = []
                    for tweetline in text.split('\n'):
                        if not tweetline:
                            continue
                        if len(tweetlines) == 0:
                            username = irc_color(f'@{username}', 'orange', reset=True)
                            blue_loser = irc_color(' [LOSER ALERT]', 'royal', reset=True) if verified else ''
                            tweetlines.append(f'{username}{blue_loser}: {tweetline}')
                        else:
                            tweetlines.append(f'{tweetline}')
                    lines.extend(tweetlines)
                except Exception: # pylint: disable=broad-except
                    pass
        return lines
