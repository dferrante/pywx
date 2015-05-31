import datetime
import requests
from . import base
from registry import register


hms = lambda s: ''.join(['%s%s' % (n,l) for n,l in filter(lambda x: bool(x[0]), [(s/60/60, 'h'), (s/60%60, 'm'), (s%60%60, 's')])])

@register(commands=['buttcoin',])
class Buttcoin(base.Command):
    buttcoin_api = 'http://api.bitcoincharts.com/v1/markets.json'
    default_symbol = 'btceUSD'

    template = """{{ symbol|nc }} ({{ currency|c('green') }}):
        {{ 'Last'|tc }}: ${{ close }} ($1 = {{ inverse }})
        {{ 'High'|tc }}: ${{ high }}
        {{ 'Low'|tc }}: ${{ low }}
        {{ 'Volume'|tc }}: {{ volume }}
        {{ 'Bid'|tc }}: ${{ bid }}
        {{ 'Ask'|tc }}: ${{ ask }}
        {{ 'Last Trade'|tc }}: {{ last_trade }} ({{ ago }} ago)"""

    def context(self, msg):
        resp = requests.get(self.buttcoin_api)
        markets = resp.json()

        mdict = {}
        for market in markets:
            mdict[market['symbol']] = market

        symbol = self.default_symbol
        if len(msg['args']) > 1:
            symbol = msg['args'][1]
        market = mdict.get(symbol, mdict.get(self.default_symbol))
        if not market:
            return ''

        market['inverse'] = round(1.0/int(market['close']), 5)
        last_trade = datetime.datetime.fromtimestamp(market['latest_trade'])
        market['last_trade'] = last_trade.strftime("%Y-%m-%d %H:%M:%S EST")
        market['ago'] = hms((datetime.datetime.now()-last_trade).seconds)

        return market
