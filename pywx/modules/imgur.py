from .base import ParserCommand, cmap
from registry import register_parser
from imgurpython import ImgurClient
import urlparse
import re

imgur_regexes = (
    ('get_image', re.compile('https?://i.imgur.com/([\w]+)\.([\w]+)')),
    ('get_image', re.compile('https?://imgur.com/([^/]+)$')),
    ('get_album', re.compile('https?://imgur.com/a/([^/]+)$')),
    ('get_album', re.compile('https?://imgur.com/gallery/([^/]+)$')),
)


@register_parser
class ImgurParser(ParserCommand):
    def __init__(self, config):
        super(ImgurParser, self).__init__(config)
        self.client = ImgurClient(self.config['imgur_id'], self.config['imgur_secret'])

    def get_id_from_regex(self, regex, word):
        match = regex.match(word)
        if match:
            img_id = match.group(1)
            return img_id
        return None

    def parse(self, msg):
        lines = []
        for word in msg['msg'].split():
            try:
                for getter, regex in imgur_regexes:
                    img_id = self.get_id_from_regex(regex, word)
                    if img_id:
                        img = getattr(self.client, getter)(img_id)
                        if hasattr(img, 'nsfw') and img.nsfw:
                            lines.append("%s%sNSFW!%s" % (cmap['bold'], cmap['red'], cmap['reset']))
                            break
            except:
                continue

        return lines
