import logging
from urllib.parse import urlparse

import tweepy

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

                    client = tweepy.Client(self.config["twitter_token"])
                    data = client.get_tweet(twid, tweet_fields='entities', user_fields='verified')
                    tweet = data.data.data
                    text = tweet['text']

                    user_data = client.get_user(username=username, user_fields='verified')
                    verified = user_data.data.data['verified']

                    for url in tweet.get('entities', {}).get('urls', []):
                        text = text.replace(url['url'], url['expanded_url'])

                    tweetlines = []
                    for tweetline in text.split('\n'):
                        if not tweetline:
                            continue
                        if len(tweetlines) == 0:
                            username = irc_color(f'@{username}', 'orange', reset=True)
                            blue_loser = irc_color('[LOSER ALERT]', 'royal', reset=True) if verified else ''
                            tweetlines.append(f'{username} {blue_loser}: {tweetline}')
                        else:
                            tweetlines.append(f'{tweetline}')
                    lines.extend(tweetlines)
                except Exception: # pylint: disable=broad-except
                    logging.exception("twitter problem")
        return lines
