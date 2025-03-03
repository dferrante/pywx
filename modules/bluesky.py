from urllib.parse import urlparse, unquote

from atproto import Client

from .base import ParserCommand, irc_color
from .registry import register_parser


@register_parser
class BlueskyParser(ParserCommand):
    multiline = True

    def parse(self, msg):
        if not self.config.get("bluesky_username") or not self.config.get("bluesky_password"):
            return []

        lines = []

        for word in msg['msg'].split(' '):
            url = urlparse(word)
            if 'bsky.app' in url.netloc:
                path_parts = url.path.strip('/').split('/')
                if (len(path_parts) >= 4 and path_parts[0] == 'profile' and path_parts[2] == 'post'):
                    handle = unquote(path_parts[1])
                    post_rkey = path_parts[3]

                    try:
                        client = Client()
                        client.login(self.config['bluesky_username'], self.config['bluesky_password'])

                        # resolve handle to DID
                        res = client.com.atproto.identity.resolve_handle({'handle': handle})
                        did = res['did']

                        uri = f"at://{did}/app.bsky.feed.post/{post_rkey}"
                        post_thread = client.app.bsky.feed.get_post_thread({'uri': uri, 'depth': 0})

                        # extract post content
                        content = post_thread['thread']['post']['record']['text']
                        try:
                            images = post_thread['thread']['post']['embed']['images']
                            if len(images) == 1:
                                content += f" {images[0]['fullsize']}"
                            elif len(images) > 1:
                                content += f" {images[0]['fullsize']} +{len(images) - 1} more"
                        except Exception: #nosec
                            pass
                        try:
                            if 'embed.video' in post_thread['thread']['post']['embed']['media']['py_type']:
                                content += " [+video]"
                        except Exception: #nosec
                            pass
                        try:
                            if 'embed.external' in post_thread['thread']['post']['embed']['external']['py_type']:
                                content += f" {post_thread['thread']['post']['embed']['external']['uri']}"
                        except Exception: #nosec
                            pass
                        display_handle = irc_color(f'@{handle}', 'blue', reset=True)
                        lines = f"{irc_color(display_handle, 'orange')}: {content}".split('\n')
                        lines = filter(None, lines)

                    except Exception: #nosec
                        pass

        return lines
