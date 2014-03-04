import sys
import socket
import string
import time
import datetime
import logging as log
log.basicConfig(level=log.DEBUG)


class Pythabot:
    def __init__(self,config):
        self.config = config
        self.buffer = ""
        self.debounce = False
        self.debounce2 = False
        self.commands = {}
        self.commandlist = []
        self.periodiccommandlist = []
        self.sock = socket.socket()

    def connect(self):
        try:
            self.sock.connect((self.config["host"],self.config["port"]))
            log.info("Connected to %s" % self.config["host"])

            if len(self.config["pass"]) != 0:
                self.sendraw("PASS %s" % self.config["pass"])
            else:
                log.info("Account identification bypassed.")

            self.sendraw("NICK %s" % self.config["nick"])
            self.sendraw("USER %s %s bla :%s" % (self.config["ident"], self.config["host"], self.config["realname"]))
            log.info("Identified as %s" % self.config["nick"])
        except socket.error:
            self.quit("Could not connect to port %s, on %s." % (self.config["port"], self.config["host"]))

    def addCommand(self, text, func, permission):
        self.commands[text] = {"func": func, "permission": permission}
        self.commandlist.append(text)

    def addPeriodicCommand(self, func):
        self.periodiccommandlist.append(func)

    def initparse(self,line):
        #[':techboy6601!~IceChat77@unaffiliated/techboy6601','PRIVMSG','#botters-test',':yo','wuts','up']
        senderline = line[0]
        chan = line[2]
        msg = " ".join(line[3:])
        msg = msg[1:]
        args = msg.split(" ")
        firstarg = args[0]
        exapoint = senderline.find("!")
        tildepoint = senderline.find("~") + 1
        atpoint = senderline.find("@") + 1
        sender = senderline[1:exapoint]
        ident = senderline[tildepoint:atpoint-1]
        mask = senderline[atpoint:]

        parseinfo = {
            "sender":sender,
            "ident":ident,
            "mask":mask,
            "chan":chan,
            "msg":msg,
            "firstarg":firstarg,
            "args":args
            }
        self.parse(parseinfo)

    def parse(self, parseinfo):
        msg = parseinfo["firstarg"]
        if msg in self.commands:
            log.info('got command %s %s' % (msg, parseinfo))
            if self.commands[msg]["permission"] == "owner":
                if parseinfo["mask"] == self.config["ownermask"]:
                    self.commands[msg]["func"](parseinfo)

            if self.commands[msg]["permission"] == "all":
                self.commands[msg]["func"](parseinfo)

    def listen(self):
        try:
            while 1:
                self.buffer = self.buffer + self.sock.recv(1024)
                log.debug(self.buffer)
                if (("/MOTD" in self.buffer or 'End of message of the day' in self.buffer) and self.debounce == False):
                    for chan in self.config["chans"]:
                        self.sendraw("JOIN %s" % chan)
                        log.info("Joined %s" % chan)
                        self.debounce == True

                temp = self.buffer.split("\n")
                self.buffer = temp.pop()

                for line in temp:
                    line = string.rstrip(line)
                    line = line.split(" ")

                    if line[1] == "433":
                        self.quit("Username '%s' is already in use! Aborting." % self.config["nick"])

                    if line[0] == "PING":
                        self.sendraw("PONG %s" % line[1])
                        log.debug("PONG %s %s" % (line[1], datetime.datetime.now()))
                        for func in self.periodiccommandlist:
                            func({'chan': '#mefi'})

                    if line[1] == "PRIVMSG":
                        self.initparse(line)
        except socket.error:
            log.error("Socket error. Reconnecting in 30s")
            time.sleep(30)
            self.connect()

    def sendraw(self,msg):
        self.sock.send(msg + "\r\n")

    def privmsg(self,to,msg):
        self.sock.send("PRIVMSG %s :%s\r\n" % (to, msg.encode('utf-8')))

    def quit(self,errmsg):
        log.error("%s" % errmsg)
        self.sendraw("QUIT :%s" % self.config["quitmsg"])
        self.sock.close()
        sys.exit(1)
