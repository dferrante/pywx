
def quit(parseinfo):
    bot.quit("Quit")

def debug(parseinfo):
    import ipdb
    ipdb.set_trace()

def colors(parseinfo):
    bot.privmsg(parseinfo['chan'], " - ".join(["%s%s\x030" % (v,k) for k,v in cmap.items()]))
