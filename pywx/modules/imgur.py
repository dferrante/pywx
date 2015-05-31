from .base import ParserCommand
from registry import register_parser
from imgurpython import ImgurClient
import urlparse
import re


imgur_img_re = re.compile('https?://i.imgur.com/([\w]+)\.([\w]+)')
imgur_page_re = re.compile('https?://imgur.com/([\w]+)$')


@register_parser
class ImgurParser(ParserCommand):
    def __init__(self, config):
        super(ImgurParser, self).__init__(config)
        self.client = ImgurClient(self.config['imgur_id'], self.config['imgur_secret'])

    def parse(self, msg):
        lines = []
        for word in msg['msg'].split():
            img, album = None, None

            try:
                url = urlparse.urlparse(word)
                if 'imgur' in url.netloc:
                    img = imgur_img_re.match(word)
                    if img:
                        img_id = img.group(1)
                        img = self.client.get_image(img_id)
                        if img.title:
                            lines.append("IMGUR: %s" % (img.title))
            except:
                continue

        return lines
