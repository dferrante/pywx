import requests

from . import base
from .registry import register


def hms(secs):
    return ''.join([f'{n}{l}' for n,l in filter(lambda x: bool(x[0]), [(secs / 60 / 60, 'h'), (secs / 60 % 60, 'm'), (secs % 60 % 60, 's')])])


@register(commands=['buttcoin',])
class Buttcoin(base.Command):
    buttcoin_api = 'https://api.binance.com/api/v3/ticker/24hr'

    template = """{{ symbol|nc }}:
        {{ 'Last'|tc }}: ${{ close }} ($1 = {{ inverse }})
        {{ 'Change'|tc }}: {{ change|c(color) }} {{ change_per|c(color) }}
        {{ 'High'|tc }}: ${{ high }}
        {{ 'Low'|tc }}: ${{ low }}
        {{ 'Volume'|tc }}: {{ volume }}
        {{ 'Bid'|tc }}: ${{ bid }}
        {{ 'Ask'|tc }}: ${{ ask }})"""

    def parse_args(self, msg):
        parser = base.IRCArgumentParser()
        parser.add_argument('symbol', type=str, default='BTCUSDT', nargs=1)
        return parser.parse_args(msg)

    def context(self, msg):
        args = self.parse_args(msg)

        resp = requests.get(self.buttcoin_api, params={'symbol': args.symbol[0]})
        market = resp.json()

        if 'code' in market:
            return ''

        market['symbol'] = args.symbol[0]
        market['close'] = round(float(market['lastPrice']), 2)
        if float(market['lastPrice']) > 0:
            market['inverse'] = round(1.0 / float(market['lastPrice']), 5)
        else:
            market['inverse'] = 0
        market['change'] = round(float(market['priceChange']), 2)
        market['change_per'] = f"{round(float(market['priceChangePercent']), 2)}%"
        market['high'] = round(float(market['highPrice']), 2)
        market['low'] = round(float(market['lowPrice']), 2)
        market['volume'] = round(float(market['volume']), 2)
        market['bid'] = round(float(market['bidPrice']), 2)
        market['ask'] = round(float(market['askPrice']), 2)
        market['color'] = 'green' if market['change'] > 0 else 'red'
        return market

# {
#     "symbol": "BTCUSDT",
#     "priceChange": "-408.67000000",
#     "priceChangePercent": "-1.969",
#     "weightedAvgPrice": "20654.47500474",
#     "prevClosePrice": "20752.38000000",
#     "lastPrice": "20343.70000000",
#     "lastQty": "0.02881000",
#     "bidPrice": "20343.69000000",
#     "bidQty": "0.82071000",
#     "askPrice": "20343.70000000",
#     "askQty": "2.22681000",
#     "openPrice": "20752.37000000",
#     "highPrice": "21212.10000000",
#     "lowPrice": "20152.00000000",
#     "volume": "63307.59171000",
#     "quoteVolume": "1307585070.58433960",
#     "openTime": 1656390824190,
#     "closeTime": 1656477224190,
#     "firstId": 1427404613,
#     "lastId": 1428465557,
#     "count": 1060945
# }
