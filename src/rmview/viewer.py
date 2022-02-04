from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

def _invertColor(c):
  (r, g, b, a) = c.getRgb()
  return QColor(255-r, 255-g, 255-b, a)


class QtImageViewer(QGraphicsView):

  pointerEvent = pyqtSignal(int, int, int)
  _button = 0

  zoomInFactor = 1.25
  zoomOutFactor = 1 / zoomInFactor

  _fit = True
  _rotation = 0 # used to produce a rotated screenshot
  _invert_colors = False


  def __init__(self):
    QGraphicsView.__init__(self)
    self.setFrameStyle(QFrame.Shape.NoFrame)

    self.setRenderHint(QPainter.RenderHint.Antialiasing)
    self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    self.viewport().grabGesture(Qt.GestureType.PinchGesture)

    self.scene = QGraphicsScene()
    self.setScene(self.scene)

    self._pixmap = None
    self.aspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    ### ACTIONS
    self.fitAction = QAction('Fit to view', self, checkable=True)
    self.fitAction.setShortcut("Ctrl+0")
    self.fitAction.triggered.connect(lambda: self.setFit(True))
    self.addAction(self.fitAction)
    ###
    self.actualSizeAction = QAction('Actual Size', self)
    self.actualSizeAction.setShortcut("Ctrl+1")
    self.actualSizeAction.triggered.connect(lambda: self.actualSize())
    self.addAction(self.actualSizeAction)
    ###
    self.zoomInAction = QAction('Zoom In', self)
    self.zoomInAction.setShortcut(QKeySequence.StandardKey.ZoomIn)
    self.zoomInAction.triggered.connect(self.zoomIn)
    self.addAction(self.zoomInAction)
    ###
    self.zoomOutAction = QAction('Zoom Out', self)
    self.zoomOutAction.setShortcut(QKeySequence.StandardKey.ZoomOut)
    self.zoomOutAction.triggered.connect(self.zoomOut)
    self.addAction(self.zoomOutAction)
    ###
    self.rotCWAction = QAction('Rotate clockwise', self)
    self.rotCWAction.setShortcut("Ctrl+R")
    self.rotCWAction.triggered.connect(self.rotateCW)
    self.addAction(self.rotCWAction)
    ###
    self.rotCCWAction = QAction('Rotate counter-clockwise', self)
    self.rotCCWAction.setShortcut("Ctrl+L")
    self.rotCCWAction.triggered.connect(self.rotateCCW)
    self.addAction(self.rotCCWAction)
    ###
    self.invertColorsAction = QAction('Invert colors', checkable=True, checked=self.isInverted())
    self.invertColorsAction.setShortcut("Ctrl+I")
    self.invertColorsAction.triggered.connect(self.invertColors)
    self.addAction(self.invertColorsAction)
    ###
    self.screenshotAction = QAction('Save screenshot', self)
    self.screenshotAction.setShortcut(QKeySequence.StandardKey.Save)
    self.screenshotAction.triggered.connect(self.screenshot)
    self.addAction(self.screenshotAction)
    ###

    self.menu = QMenu(self)
    self.menu.addAction(self.fitAction)
    self.menu.addAction(self.actualSizeAction)
    self.menu.addAction(self.zoomInAction)
    self.menu.addAction(self.zoomOutAction)
    self.menu.addSeparator() # --------------------------
    self.menu.addAction(self.rotCWAction)
    self.menu.addAction(self.rotCCWAction)
    self.menu.addSeparator() # --------------------------
    self.menu.addAction(self.invertColorsAction)
    self.menu.addSeparator() # --------------------------
    self.menu.addAction(self.screenshotAction)

  def contextMenuEvent(self, event):
    self.fitAction.setChecked(self._fit)
    self.invertColorsAction.setChecked(self._invert_colors)
    self.menu.exec(self.mapToGlobal(event.pos()))

  def hasImage(self):
    return self._pixmap is not None

  def clearImage(self):
    if self.hasImage():
      self.scene.removeItem(self._pixmap)
      self._pixmap = None

  def pixmap(self):
    if self.hasImage():
      return self._pixmap.pixmap()
    return None

  def image(self):
    if self.hasImage():
      return self._pixmap.pixmap().toImage()
    return None

  def setImage(self, image):
    if type(image) is QImage:
      if self._invert_colors:
        image.invertPixels()
      pixmap = QPixmap.fromImage(image)
    else:
      raise RuntimeError("ImageViewer.setImage: Argument must be a QImage.")
    if self.hasImage():
      self._pixmap.setPixmap(pixmap)
    else:
      self._pixmap = self.scene.addPixmap(pixmap)
      self._pixmap.setZValue(-1)
    self._pixmap.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
    self.setSceneRect(QRectF(pixmap.rect()))  # Set scene size to image size.
    # self.fitInView(self.sceneRect(), self.aspectRatioMode)  # Show entire image (use current aspect ratio mode).
    self.updateViewer()

  def updateViewer(self):
    if self.hasImage() is None:
      return
    if self._fit:
      self.fitInView(self.sceneRect(), self.aspectRatioMode)
    # else:

  def resizeEvent(self, event):
    self.updateViewer()

  def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      scenePos = self.mapToScene(event.pos())
      if int(event.modifiers()) & int(Qt.KeyboardModifier.ControlModifier):
        self._button = 1
      else:
        self._button = 4
      self.pointerEvent.emit(int(scenePos.x()), int(scenePos.y()), self._button)

  def mouseReleaseEvent(self, event):
    scenePos = self.mapToScene(event.pos())
    self._button = 0
    self.pointerEvent.emit(int(scenePos.x()), int(scenePos.y()), 0)

  def mouseMoveEvent(self, event):
    if self._button > 0:
      scenePos = self.mapToScene(event.pos())
      self.pointerEvent.emit(int(scenePos.x()), int(scenePos.y()), self._button)

  def mouseDoubleClickEvent(self, event):
    # scenePos = self.mapToScene(event.pos())
    if event.button() == Qt.LeftButton:
        self._fit=True
        self.updateViewer()
        # self.leftMouseButtonDoubleClicked.emit(scenePos.x(), scenePos.y())
    # elif event.button() == Qt.RightButton:
        # self.rightMouseButtonDoubleClicked.emit(scenePos.x(), scenePos.y())
    QGraphicsView.mouseDoubleClickEvent(self, event)

  def viewportEvent(self, event):
    if event.type() == QEvent.Type.Gesture:
      pinch = event.gesture(Qt.GestureType.PinchGesture)
      if pinch is not None:
        self._fit = False
        self.scale(pinch.scaleFactor(), pinch.scaleFactor())
        return True
    return bool(QGraphicsView.viewportEvent(self, event))

  def wheelEvent(self, event):
    if event.modifiers() == Qt.KeyboardModifier.NoModifier:
      QGraphicsView.wheelEvent(self, event)
    else:
      self._fit = False

      self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
      self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

      oldPos = self.mapToScene(event.pos())

      # Zoom
      if event.angleDelta().y() > 0:
          zoomFactor = self.zoomInFactor
      else:
          zoomFactor = self.zoomOutFactor
      self.scale(zoomFactor, zoomFactor)

      # Get the new position
      newPos = self.mapToScene(event.pos())

      # Move scene to old position
      delta = newPos - oldPos
      self.translate(delta.x(), delta.y())

  def screenshot(self):
    img = self.image()
    if img is not None:
      fileName, ok = QFileDialog.getSaveFileName(self, "Save screenshot...", "rm-screenshot.png")
      if ok and fileName:
        img = img.transformed(QTransform().rotate(self._rotation))
        img.save(fileName)

  def invertColors(self):
    self._invert_colors = not self._invert_colors
    if self._pixmap:
      img = self._pixmap.pixmap().toImage()
      if not self._invert_colors:
        img.invertPixels()
      self.setImage(img)
    self.setBackgroundBrush(_invertColor(self.backgroundBrush().color()))

  def isInverted(self):
    return self._invert_colors

  def isLandscape(self):
    return self._rotation == 90

  def landscape(self):
    self.resetTransform()
    self.rotate(90)
    self._rotation = 90
    self.updateViewer()

  def isPortrait(self):
    return self._rotation == 0

  def portrait(self):
    self.resetTransform()
    self._rotation = 0
    self.updateViewer()

  def rotateCW(self):
    self.rotate(90)
    self._rotation += 90
    if not self.windowState() in [QWindow.Visibility.FullScreen, QWindow.Visibility.Maximized]:
      s = QGuiApplication.primaryScreen().availableGeometry().size()
      self.resize(self.size().transposed().boundedTo(s))
    self.updateViewer()

  def rotateCCW(self):
    self.rotate(-90)
    self._rotation -= 90
    if not self.windowState() in [QWindow.Visibility.FullScreen, QWindow.Visibility.Maximized]:
      s = QGuiApplication.primaryScreen().availableGeometry().size()
      self.resize(self.size().transposed().boundedTo(s))
    self.updateViewer()

  def zoomIn(self):
    self._fit = False
    self.scale(self.zoomInFactor, self.zoomInFactor)

  def zoomOut(self):
    self._fit = False
    self.scale(self.zoomOutFactor, self.zoomOutFactor)

  def setFit(self, f):
    self._fit = f
    self.updateViewer()

  def actualSize(self):
    self._fit = False
    self.resetTransform()
    self.scale(1/self.devicePixelRatio(), 1/self.devicePixelRatio())
    self.rotate(self._rotation)

  def keyPressEvent(self, event):
    if event.key() == Qt.Key.Key_F:
      self.setFit(True)
    elif event.key() == Qt.Key.Key_1:
      self.actualSize()
    elif event.key() == Qt.Key.Key_S:
      self.screenshot()
    elif event.key() == Qt.Key.Key_Plus:
      self.zoomIn()
    elif event.key() == Qt.Key.Key_Minus:
      self.zoomOut()

