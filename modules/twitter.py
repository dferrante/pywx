import math
from urllib.parse import urlparse

import requests

from .base import ParserCommand, irc_color
from .registry import register_parser


@register_parser
class TwitterParser(ParserCommand):
    multiline = True

    def get_token(self, id):
        token = (int(id) / 1e15) * math.pi
        token_str = format(token, f'.{6 ** 2}f')
        return token_str.replace('0', '').replace('.', '')

    def fetch_tweet(self, id):
        url = "https://cdn.syndication.twimg.com/tweet-result"
        params = {
            'id': id,
            'lang': 'en',
            'features': ';'.join([
                'tfw_timeline_list:',
                'tfw_follower_count_sunset:true',
                'tfw_tweet_edit_backend:on',
                'tfw_refsrc_session:on',
                'tfw_fosnr_soft_interventions_enabled:on',
                'tfw_show_birdwatch_pivots_enabled:on',
                'tfw_show_business_verified_badge:on',
                'tfw_duplicate_scribes_to_settings:on',
                'tfw_use_profile_image_shape_enabled:on',
                'tfw_show_blue_verified_badge:on',
                'tfw_legacy_timeline_sunset:true',
                'tfw_show_gov_verified_badge:on',
                'tfw_show_business_affiliate_badge:on',
                'tfw_tweet_edit_frontend:on',
            ]),
            'token': self.get_token(id)
        }

        response = requests.get(url, params=params, timeout=10)
        is_json = 'application/json' in response.headers.get('Content-Type', '')

        if response.ok:
            data = response.json() if is_json else None
            if data and data.get('__typename') == 'TweetTombstone':
                return None
            return data
        return None

    def parse(self, msg):
        lines = []
        for word in msg['msg'].split(' '):
            url = urlparse(word)
            if 'twitter' in url.netloc or url.netloc == 'x.com':
                path = url.path
                try:
                    username = path.split('/')[1]
                    twid = path.split('/')[3]

                    tweet = self.fetch_tweet(twid)
                    text = tweet['text']

                    tweetlines = []
                    for tweetline in text.split('\n'):
                        if not tweetline:
                            continue
                        if len(tweetlines) == 0:
                            username = irc_color(f'@{username}', 'orange', reset=True)
                            tweetlines.append(f'{username}: {tweetline}')
                        else:
                            tweetlines.append(f'{tweetline}')
                    lines.extend(tweetlines)
                except Exception: # pylint: disable=broad-except # nosec
                    pass
        return lines
