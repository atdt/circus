import errno
import os
import tempfile
import traceback
import zmq

from circus import logger
from circus.exc import AlreadyExist, MessageError
from circus.sighandler import SysHandler
from circus.show import Show


class Controller(object):
    def __init__(self, context, endpoint, trainer, timeout=1.0):
        self.context = context
        self.skt = self.context.socket(zmq.ROUTER)
        self.skt.bind(endpoint)
        self.poller = zmq.Poller()
        self.poller.register(self.skt, zmq.POLLIN)

        self.trainer = trainer
        self.timeout = timeout * 1000

        # start the sys handler
        self.sys_hdl = SysHandler(trainer)

    def send(self, msg):
        self.skt.send(msg)

    def poll(self):
        while True:
            try:
                events = dict(self.poller.poll(self.timeout))
            except zmq.ZMQError as e:
                if e.errno == errno.EINTR:
                    continue
                else:
                    return
            else:
                break

        for client in events:
            _id = client.recv()
            msg = client.recv() or ""
            msg = msg.strip()
            if not msg:
                self.send_response(_id, client, msg,
                        "error: empty command")
                continue

            msg_parts = msg.split(" ")
            resp = ""
            handler = None
            try:
                cmd, inst, args = self.parse_message(msg_parts)
                handler = getattr(inst, "handle_%s" % cmd)
            except MessageError as e:
                resp = "error: %s" % str(e)
            except AttributeError as e:
                resp = "error: message %r" % msg

            if handler is not None:
                ## hacky part we should be abble to handlle the response
                ## before the controller stop
                if cmd in ('stop', 'quit', 'terminate') and \
                        inst == self.trainer:
                    self.send_response(_id, client, msg, "ok")

                try:
                    resp = handler(*args)
                except OSError as e:
                    resp = "error: %s" % e

                except Exception as e:
                    tb = traceback.format_exc()
                    resp = "error: command %r: %s [%s]" % (msg, str(e), tb)

            if resp is None:
                continue

            if not isinstance(resp, (str, buffer,)):
                msg = "msg %r tried to send a non-string: %s" % (msg,
                        str(resp))
                raise ValueError(msg)

            self.send_response(_id, client, msg, resp)

    def send_response(self, client_id, sock, msg, resp):
        try:
            sock.send(client_id, zmq.SNDMORE)
            sock.send(resp)
        except zmq.ZMQError as e:
            logger.error("Received %r - Could not send back %r - %s" %
                                (msg, resp, str(e)))

    def _get_show(self, show_name):
        try:
            return self.trainer.get_show(show_name)
        except KeyError:
            raise MessageError("program %s not found" % show_name)


    def parse_message(self, msg_parts):
        cmd = msg_parts[0].lower()
        args = []
        inst = self.trainer

        if len(msg_parts) > 1 and msg_parts[1]:
            show_name = msg_parts[1].lower()
            if cmd == "add_show":
                if len(msg_parts) < 3:
                    raise MessageError("invalid number of parameters")

                show_cmd = " ".join(msg_parts[2:])
                args = [show_name, show_cmd]
            elif cmd == "del_show":
                self._get_show(show_name)
                args = [show_name]
            else:
                inst = self._get_show(show_name)
                if len(msg_parts) > 2:
                    args = msg_parts[2:]

        return cmd, inst, args
