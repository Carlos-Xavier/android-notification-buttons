import sys
sys.path.append('../')
from app_modules.noti_builder import NotificationBuilder
from app_modules.simple_tcp.server import SimpleServer
from kivy.utils import platform
from kivy.logger import Logger
from plyer.compat import PY2
from time import sleep
from sys import path
import traceback
import json
if platform == 'android':
    '''SDL2 service activity audio is currently bugged, we use native android
    player instead'''
    from app_modules.android_media_player import MediaPlayer
else:
    from app_modules.media_player import MediaPlayer

if PY2:
    from Queue import Queue
else:
    from queue import Queue


class AppService(object):
    beep_path = '../audio/beep1.wav'
    rain_path = '../audio/rain.ogg'
    nbuilder = NotificationBuilder()
    intent_queue = Queue()
    server = SimpleServer()
    new_toolchain = False
    looping = True
    client = None

    def __init__(self, new_toolchain=False):
        self.new_toolchain = new_toolchain
        if new_toolchain:
            self.beep_path = '%s/audio/beep1.wav' % (path[4])
            self.rain_path = '%s/audio/rain.ogg' % (path[4])
        self.server.on_connect = self.on_connect
        self.server.on_disconnect = self.on_disconnect
        self.mplayer = MediaPlayer(
            self.rain_path,
            on_play=self.on_mplayer_play, on_pause=self.on_mplayer_pause)
        try:
            self.server.start()
        except:
            while True:
                Logger.info(
                    'AppService: __init__: Failed to start server, '
                    'retrying in 3 sec')
                sleep(3)
                try:
                    self.server.start()
                    break
                except:
                    pass
        self.msg_handler_switch = {
            'mplayer_play': self.mplayer.play,
            'mplayer_pause': self.mplayer.pause,
        }
        self.make_media_notification(False)
        self.service_loop()

    def make_media_notification(self, is_playing):
        if platform == 'android':
            b2 = NotificationBuilder()
            if self.new_toolchain:
                b2.set_id(0)
            else:
                b2.set_id(1)
            b2.set_title('Media Service')
            b2.set_ticker('Starting media service')
            if is_playing:
                b2.set_message('Playing')
            else:
                b2.set_message('Paused')
            if not b2.buttons:
                b2.add_button(
                    'Play', 17301540, self.intent_callback, action='Play')
                b2.add_button(
                    'Pause', 17301539, self.intent_callback, action='Pause')
            b2.set_ongoing(True)
            b2.set_autocancel(False)
            b2.build()

    def intent_callback(self, intent, *arg):
        # BroadcastReceiver callbacks are done on a different thread
        # and can crash the service on unsafe tasks, puting in queue is safe
        # self.intent_queue.put(intent)
        print('EEE', 'intent_callback', intent)

    def on_connect(self, client):
        Logger.info('AppService: client connected')
        self.client = client

    def on_disconnect(self, client):
        Logger.info('AppService: client disconnected')
        self.client = None

    def service_loop(self):
        Logger.info('AppService: service_loop: started')
        try:
            while self.looping:
                msg = None
                msg = self.server.read_queue()
                if msg:
                    self.handle_msg(*msg)

                if not self.intent_queue.empty():
                    self.current_instr = self.intent_queue.get()
                sleep(0.1)

        except Exception as e:
            traceback.print_exc()
            self.client.send_msg('AppService: service_loop crashed: {}'.format(
                traceback.format_exc()))

    def on_mplayer_play(self):
        Logger.info('AppService: on_mplayer_play()')
        self.send_msg('MediaPlayer: play()')
        self.make_media_notification(True)

    def on_mplayer_pause(self):
        Logger.info('AppService: on_mplayer_pause()')
        self.send_msg('MediaPlayer: pause at {}'.format(
            self.mplayer.pause_time))
        self.make_media_notification(False)

    def handle_msg(self, client, msg):
        mdict = json.loads(str(msg))
        Logger.info('AppService: {}'.format(mdict))
        if mdict[u'method'] == u'build_notification':
            kw = mdict[u'kwargs']
            for k in (
                u'id', u'ticker', u'subtext', u'message', u'ongoing',
                u'autocancel', u'title'):
                self.nbuilder.kwargs[k] = kw[k]
            if kw[u'vibrate']:
                self.nbuilder.kwargs[u'vibrate'] = 1.0
            else:
                self.nbuilder.kwargs[u'vibrate'] = 0.0
            if kw[u'sound']:
                self.nbuilder.kwargs[u'sound'] = '../audio/beep1.wav'
            else:
                self.nbuilder.kwargs[u'sound'] = ''
            self.nbuilder.build()
        elif mdict[u'method'] == u'remove_notification':
            self.nbuilder.remove_notification(id=mdict[u'kwargs'][u'id'])
        else:
            self.msg_handler_switch[mdict[u'method']]()

    def send_msg(self, msg):
        sleep(0.03)
        if self.client:
            self.client.send_msg(msg)

    def stop(self):
        self.looping = True
