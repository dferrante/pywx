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

                        res = client.com.atproto.identity.resolve_handle({'handle': handle})
                        did = res['did']

                        uri = f"at://{did}/app.bsky.feed.post/{post_rkey}"
                        post_thread = client.app.bsky.feed.get_post_thread({'uri': uri, 'depth': 0})

                        # handle post
                        record = post_thread['thread']['post']['record']
                        content = record.get('text', '')
                        display_handle = irc_color(f'@{handle}', 'blue', reset=True)
                        line = f"{display_handle}: {content}"

                        # handle images
                        images = record.get('images', [])
                        if images:
                            image_urls = [img.get('url') for img in images if img.get('url')]
                            if image_urls:
                                line += " " + " ".join(image_urls)

                        # handle external links
                        if record.get('external'):
                            external_url = record['external'].get('uri')
                            if external_url:
                                line += f" {external_url}"

                        lines.append(line)

                    except Exception:
                        pass

        return lines
