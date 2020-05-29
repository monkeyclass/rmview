from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from rmparams import *

import paramiko
import struct
import time

import sys
import os
import logging
log = logging.getLogger('rmview')


from twisted.internet.protocol import Protocol
from twisted.internet import protocol, reactor
from twisted.application import internet, service

from rfb import *

IMG_FORMAT = QImage.Format_Grayscale16
BYTES_PER_PIXEL = 2


class FBWSignals(QObject):
  onFatalError = pyqtSignal(Exception)
  onNewFrame = pyqtSignal(QImage)

def _zrle_next_bit(it, pixels_in_tile):
    num_pixels = 0
    while True:
        b = ord(next(it))

        for n in range(8):
            value = b >> (7 - n)
            yield value & 1

            num_pixels += 1
            if num_pixels == pixels_in_tile:
                return


def _zrle_next_dibit(it, pixels_in_tile):
    num_pixels = 0
    while True:
        b = ord(next(it))

        for n in range(0, 8, 2):
            value = b >> (6 - n)
            yield value & 3

            num_pixels += 1
            if num_pixels == pixels_in_tile:
                return


def _zrle_next_nibble(it, pixels_in_tile):
    num_pixels = 0
    while True:
        b = ord(next(it))

        for n in range(0, 8, 4):
            value = b >> (4 - n)
            yield value & 15

            num_pixels += 1
            if num_pixels == pixels_in_tile:
                return


class RFBTest(RFBClient):
  img = QImage(WIDTH, HEIGHT, IMG_FORMAT)
  painter = QPainter(img)

  def vncConnectionMade(self):
    self.signals = self.factory.signals
    self.setEncodings([
      HEXTILE_ENCODING,
      CORRE_ENCODING,
      RRE_ENCODING,
      RAW_ENCODING ])
    self.framebufferUpdateRequest()


  def commitUpdate(self, rectangles=None):
    self.signals.onNewFrame.emit(self.img)
    self.framebufferUpdateRequest(incremental=1)

  def updateRectangle(self, x, y, width, height, data):
    if (width == WIDTH) and (height == HEIGHT):
      self.painter.end()
      self.img = QImage(data, WIDTH, HEIGHT, WIDTH * BYTES_PER_PIXEL, IMG_FORMAT)
      self.painter = QPainter(self.img)
    else:
      self.painter.drawImage(x,y,QImage(data, width, height, width * BYTES_PER_PIXEL, IMG_FORMAT))



class RFBTestFactory(RFBFactory):
  """test factory"""
  protocol = RFBTest

  def __init__(self, signals):
    super(RFBTestFactory, self).__init__()
    self.signals = signals

  def clientConnectionLost(self, connector, reason):
    print(reason)
    # connector.connect()

  def clientConnectionFailed(self, connector, reason):
    print("connection failed:", reason)
    reactor.callFromThread(reactor.stop)


class FrameBufferWorker(QRunnable):

  _stop = False

  def __init__(self, ssh, delay=None, lz4_path=None, img_format=IMG_FORMAT):
    super(FrameBufferWorker, self).__init__()
    self._read_loop = """\
      while dd if=/dev/fb0 count=1 bs={bytes} 2>/dev/null; do {delay}; done | {lz4_path}\
    """.format(bytes=TOTAL_BYTES,
               delay="sleep "+str(delay) if delay else "true",
               lz4_path=lz4_path or "$HOME/lz4")
    self.ssh = ssh
    self.img_format = img_format

    self.signals = FBWSignals()

  def stop(self):
    print("Stopping")
    reactor.callFromThread(reactor.stop)
    self.ssh.exec_command("killall rM-vnc-server")
    print("Stopped")
    self._stop = True

  @pyqtSlot()
  def run(self):
    _,out,_ = self.ssh.exec_command("insmod mxc_epdc_fb_damage.ko")
    out.channel.recv_exit_status()
    _,_,out = self.ssh.exec_command("$HOME/rM-vnc-server")
    print(next(out))
    self.vncClient = internet.TCPClient(self.ssh.hostname, 5900, RFBTestFactory(self.signals))
    self.vncClient.startService()
    reactor.run(installSignalHandlers=0)


class PWSignals(QObject):
  onFatalError = pyqtSignal(Exception)
  onPenMove = pyqtSignal(int, int)
  onPenPress = pyqtSignal()
  onPenLift = pyqtSignal()
  onPenNear = pyqtSignal()
  onPenFar = pyqtSignal()

LIFTED = 0
PRESSED = 1


class PointerWorker(QRunnable):

  _stop = False

  def __init__(self, ssh, threshold=1000):
    super(PointerWorker, self).__init__()
    self.ssh = ssh
    self.threshold = threshold
    self.signals = PWSignals()

  def stop(self):
    self._penkill.write('\n')
    self._stop = True

  @pyqtSlot()
  def run(self):
    penkill, penstream, _ = self.ssh.exec_command('cat /dev/input/event0 & { read ; kill %1; }')
    self._penkill = penkill
    new_x = new_y = False
    state = LIFTED

    while not self._stop:
      try:
        _, _, e_type, e_code, e_value = struct.unpack('2IHHi', penstream.read(16))
      except struct.error:
        return
      except Exception as e:
        # log.error('Error in pointer worker: %s %s', type(e), e)
        return

      # decoding adapted from remarkable_mouse
      if e_type == e_type_abs:


        # handle x direction
        if e_code == e_code_stylus_xpos:
          x = e_value
          new_x = True

        # handle y direction
        if e_code == e_code_stylus_ypos:
          y = e_value
          new_y = True

        # handle draw
        if e_code == e_code_stylus_pressure:
          if e_value > self.threshold:
            if state == LIFTED:
              # log.debug('PRESS')
              state = PRESSED
              self.signals.onPenPress.emit()
          else:
            if state == PRESSED:
              # log.debug('RELEASE')
              state = LIFTED
              self.signals.onPenLift.emit()

        if new_x and new_y:
          self.signals.onPenMove.emit(x, y)
          new_x = new_y = False

      if e_type == e_type_key and e_code == e_code_stylus_proximity:
        if e_value == 0:
          self.signals.onPenFar.emit()
        else:
          self.signals.onPenNear.emit()



