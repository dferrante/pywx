from twitch import TwitchClient
import urlparse
import datetime
from .base import ParserCommand, NoMessage, Command
from registry import register_parser, register_periodic


global twdb
twdb = None

hms = lambda s: ''.join(['%s%s' % (n,l) for n,l in filter(lambda x: bool(x[0]), [(s/60/60, 'h'), (s/60%60, 'm'), (s%60%60, 's')])])

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
                    ago = (ls['created_at'] - datetime.datetime.now()).seconds
                    lines.append("TWITCH: {} is LIVE, playing {} with {} viewers (started {} ago)".format(username, ls['game'], ls['viewers'], hms(ago)))
            except:
                continue

        return lines


class TwitchAlert(Command):
    template = u"""
        {{ 'TWITCH'|nc }}: {{ username|tc }} is {{ 'LIVE'|c('red') }}, playing {{ game|tc }} with {{ viewers|tc }} viewers (started {{ ago }} ago)
        """

    def stream_context(self, ls):
        ago = hms((ls['created_at'] - datetime.datetime.now()).seconds)
        payload = {
            'username': ls['channel']['name'],
            'game': ls['game'],
            'viewers': ls['viewers'],
            'ago': ago,
        }
        return payload


@register_periodic(60)
class TwitchAlerter(TwitchAlert):
    def get_streams(self):
        client = TwitchClient(client_id=self.config['twitch_client'], oauth_token=self.config['twitch_secret'])
        userids = []
        for user in client.users.translate_usernames_to_ids(self.config['twitch_streamers']):
            userids.append(user['id'])

        livestreams = []
        for ls in client.streams.get_live_streams(userids):
            livestreams.append(ls)
        return livestreams

    def context(self, msg):
        global twdb
        livestreams = self.get_streams()
        if twdb is None:
            twdb = []
            for ls in livestreams:
                twdb.append(ls['id'])

        for ls in livestreams:
            if ls['id'] in twdb:
                continue
            else:
                twdb.append(ls['id'])
            return self.stream_context(ls)
        raise NoMessage