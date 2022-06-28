import datetime
import requests
from . import base
from .registry import register
import bs4
import re
from decimal import Decimal


hms = lambda s: ''.join(['%s%s' % (n,l) for n,l in filter(lambda x: bool(x[0]), [(s/60/60, 'h'), (s/60%60, 'm'), (s%60%60, 's')])])

@register(commands=['wxprice',])
class NowInStock(base.Command):
    nis_api = 'http://www.nowinstock.net/{}/'
    default_path = 'computers/videocards/nvidia/gtx1080ti'

    template = """{{ maker|nc }} {{ model|nc }}:
        {% if preorder and not in_stock %}{{ "Preorder Only"|c('red', bold=True) }}{% endif %}
        {{ 'Low'|tc }}: ${{ low }}
        {{ 'High'|tc }}: ${{ high }}
        {{ 'Average'|tc }}: ${{ avg }}
        {% if last_updated %}
            {{ 'Last Updated'|tc }}: {{ last_updated }} ({{ ago }} ago)
        {% endif %}"""

    def parse_args(self, msg):
        parser = base.IRCArgumentParser()
        parser.add_argument('-p', '--path', type=str, default=[self.default_path], nargs=1, required=False)
        return parser.parse_args(msg)

    def context(self, msg):
        args = self.parse_args(msg)
        product_path = args.path[0]
        resp = requests.get(self.nis_api.format(product_path))
        if resp.status_code != 200:
            raise Exception
        doc = bs4.BeautifulSoup(resp.content, 'html.parser')
        year = datetime.datetime.now().year
        maker, model = product_path.split('/')[-2:]
        preorder = False
        in_stock = False

        tracker_div = doc.find(id='trackerContent')
        prices = []

        for product in tracker_div.find_all('tr'):
            if len(product.find_all('td')) != 4:
                continue

            p = []
            for count, row in enumerate(product.find_all('td')):
                if count == 0:
                    p.append(row.a.text)
                else:
                    p.append(row.text)
            if (p[1] == 'In Stock' or p[1] == 'Stock Available') and 'ebay' not in p[0].lower():
                in_stock = True
                price = re.sub('\$', '', re.sub(',', '', p[2]))
                prices.append(Decimal(price))
            if p[1] == 'Preorder' and 'ebay' not in p[0].lower():
                preorder = True
                price = re.sub('\$', '', re.sub(',', '', p[2]))
                prices.append(Decimal(price))

        if not prices:
            raise base.ArgumentError('{{ maker|nc }} {{ model|nc }}: Not in stock')

        prices = {
            'maker': maker,
            'model': model,
            'avg': round(sum(prices)/len(prices), 2),
            'high': max(prices),
            'low': min(prices),
            'in_stock': in_stock,
            'preorder': preorder,
        }

        try:
            history_div = doc.find(id='DisplayHistory')
            last_data = history_div.find_all('tr')[1].find_all('td')[0]
            last_updated = datetime.datetime.strptime('{} {}'.format(year, last_data.text), '%Y %b %d - %I:%M %p EST')
            prices['last_updated'] = last_updated.strftime("%Y-%m-%d %H:%M:%S EST")
            prices['ago'] = hms((datetime.datetime.now()-last_updated).seconds)
        except:
            prices['last_updated'] = None
            prices['ago'] = None
        return prices
