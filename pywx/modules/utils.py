from . import base
from .registry import register


@register(commands=['wxcolors'])
class WXcolors(base.Command):
    template = """
    {% for color in cmap %}
        {{ color|c(color) }}
    {% endfor %}
    """

    def context(self, msg):
        return {'cmap': base.cmap.keys()}
