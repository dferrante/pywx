import datetime
import logging as log
import socket
import sys
import time

log.basicConfig(level=log.INFO, format="%(asctime)-15s %(levelname)s %(message)s")


class Pythabot:
    def __init__(self, config, registry):
        self.config = config
        self.registry = registry
        self.buffer = ""
        self.debounce = False
        self.debounce2 = False
        self.sock = socket.socket()

    def connect(self):
        try:
            self.sock.connect((self.config["host"],self.config["port"]))
            log.info("Connected to %s", self.config["host"])

            if len(self.config["pass"]) != 0:
                self.sendraw(f'PASS {self.config["pass"]}')
            else:
                log.info("Account identification bypassed.")

            self.sendraw(f"NICK {self.config['nick']}")
            self.sendraw(f'USER {self.config["ident"]} {self.config["host"]} bla :{self.config["realname"]}')
            log.info("Identified as %s", self.config["nick"])
        except socket.error:
            self.quit(f'Could not connect to port {self.config["port"]}, on {self.config["host"]}.')

    def run_periodic_commands(self):
        for task, attrs in self.registry.periodic_tasks.items():
            if attrs['last_run'] and attrs['last_run'] + attrs['run_every'] >= time.time():
                continue
            else:
                log.info('Running periodic task: %s', task)
                self.registry.periodic_tasks[task]['last_run'] = time.time()
                for msg in task.run():
                    for chan in self.config['chans']:
                        self.privmsg(chan, msg)

    def initparse(self, line):
        #[':techboy6601!~IceChat77@unaffiliated/techboy6601','PRIVMSG','#botters-test',':yo','wuts','up']
        senderline = line[0]
        msg = " ".join(line[3:])
        msg = msg[1:]

        try:
            command, args = msg.split(" ", 1)
        except ValueError:
            command, args = msg, ""
        exapoint = senderline.find("!")
        tildepoint = senderline.find("~") + 1
        atpoint = senderline.find("@") + 1

        parsedline = {
            "sender": senderline[1:exapoint],
            "ident": senderline[tildepoint:atpoint - 1],
            "mask": senderline[atpoint:],
            "chan": line[2] if line[2] != self.config['nick'] else senderline[1:exapoint],
            "msg": msg,
            "command": command,
            "args": args,
            "bot": self,
        }
        self.parse(parsedline)

    def parse(self, msg):
        cmd = msg["command"].lower()
        command = self.registry.commands.get(cmd)
        if command:
            log.info('got command %s %s', cmd, msg)
            if command.permission == "all" or (command.permission == "owner" and msg["mask"] == self.config["ownermask"]):
                reply = command.run(msg)
                send_to = msg['chan'] if not command.private_only else msg['sender']
                for line in reply:
                    self.privmsg(send_to, line)

        parsed_things = []
        for parser in self.registry.parsers:
            for line in parser.parse(msg):
                parsed_things.append(line)
        if parsed_things:
            self.privmsg(msg['chan'], ' | '.join(parsed_things))

    def listen(self):
        try:
            while 1:
                self.buffer = self.buffer + self.sock.recv(1024).decode('utf-8')
                log.debug(self.buffer.strip())
                if (("MOTD" in self.buffer or 'End of message of the day' in self.buffer) and not self.debounce):
                    if 'nickserv_pass' in self.config:
                        self.privmsg('NickServ', f'identify {self.config["nickserv_pass"]}')
                        time.sleep(10)
                    for chan in self.config["chans"]:
                        self.sendraw(f"JOIN {chan}")
                        log.info("Joined %s", chan)
                    self.debounce = True

                temp = self.buffer.split("\n")
                self.buffer = temp.pop()

                for line in temp:
                    line = line.rstrip()
                    line = line.split(" ")

                    if line[1] == "433":
                        self.quit(f"Username {self.config['nick']} is already in use! Aborting.")

                    if line[0] == "PING":
                        self.sendraw(f"PONG {line[1]}")
                        log.debug(f"PONG {line[1]} {datetime.datetime.now()}")

                    if line[1] == "PRIVMSG":
                        self.initparse(line)

                self.run_periodic_commands()
        except socket.error:
            log.error("Socket error. Reconnecting in 30s")
            time.sleep(30)
            self.connect()

    def sendraw(self, msg):
        msg += "\r\n"
        self.sock.send(msg.encode('utf-8'))

    def privmsg(self, send_to, msg):
        log.info('PRIVMSG: %s', msg.encode('utf-8'))
        fullmsg = f'PRIVMSG {send_to} :{msg}\r\n'.encode('utf-8')
        self.sock.send(fullmsg)

    def quit(self, errmsg):
        log.error("%s", errmsg)
        self.sendraw(f"QUIT :{self.config['quitmsg']}")
        self.sock.close()
        sys.exit(1)
