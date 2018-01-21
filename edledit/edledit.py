#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of edledit.
# Copyright (C) 2010 Stephane Bidoul
# Copyright (C) 2018 Arne Zellentin (the Qt5 port)
#
# edledit is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# edledit is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with edledit.  If not, see <http://www.gnu.org/licenses/>.

__version__ = "0.9"

import mimetypes
import os
from datetime import timedelta

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QMainWindow, QApplication, QDialog, QComboBox, QLabel, QTimeEdit, QAbstractSpinBox, QMessageBox, QFileDialog
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

import pyedl

from edledit_ui import Ui_MainWindow
from edledit_about_ui import Ui_AboutDialog
from edledit_license_ui import Ui_LicenseDialog

# initialize mimetypes database
mimetypes.init()


def tr(s):
    return unicode(QApplication.translate("@default", s))


def timedelta2ms(td):
    return td.days*86400000 + td.seconds*1000 + td.microseconds//1000


def ms2timedelta(ms):
    return timedelta(milliseconds=ms)


class MainWindow(QMainWindow):

    steps = [
        (40, tr("40 msec")),
        (200, tr("200 msec")),
        (500, tr("0.5 sec")),
        (2000, tr("2 sec")),
        (5000, tr("5 sec")),
        (20000, tr("20 sec")),
        (60000, tr("1 min")),
        (300000, tr("5 min")),
        (600000, tr("10 min")),
    ]

    defaultStepIndex = 7

    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.settings = QtCore.QSettings("bidoul.net", "edledit")

        self.mediaObject = QMediaPlayer()
        self.mediaObject.setVideoOutput(self.ui.player)

        # initialize media components
        self.mediaObject.setNotifyInterval(200)
        self.mediaObject.mediaStatusChanged.connect(self.mediaStatusChanged)
        self.mediaObject.stateChanged.connect(self.stateChanged)
        self.mediaObject.error.connect(self.playerError)
        self.mediaObject.positionChanged.connect(self.tick)
        self.mediaObject.seekableChanged.connect(self.seekableChanged)
        self.ui.edlWidget.seek.connect(self.mediaObject.setPosition)

        # add steps combo box and position widget to toolbar
        # (this apparently can't be done in the designer)
        self.ui.stepCombobox = QComboBox(self.ui.toolBar)
        self.ui.stepLabel = QLabel(tr(" Step : "), self.ui.toolBar)
        self.ui.timeEditCurrentTime = QTimeEdit(self.ui.toolBar)
        self.ui.timeEditCurrentTime.setReadOnly(True)
        self.ui.timeEditCurrentTime.setButtonSymbols(
            QAbstractSpinBox.NoButtons)
        self.ui.posLabel = QLabel(tr(" Position : "), self.ui.toolBar)
        self.ui.timeEditCurrentTime.setDisplayFormat("HH:mm:ss.zzz")
        self.ui.toolBar.addWidget(self.ui.stepLabel)
        self.ui.toolBar.addWidget(self.ui.stepCombobox)
        self.ui.toolBar.addSeparator()
        self.ui.toolBar.addWidget(self.ui.posLabel)
        self.ui.toolBar.addWidget(self.ui.timeEditCurrentTime)

        # populate steps combo box
        for stepMs, stepText in self.steps:
            self.ui.stepCombobox.addItem(stepText)

        # initialize attributes
        self.loading = False
        self.movieFileName = None
        self.edlFileName = None
        self.edl = None
        self.edlDirty = False
        self.setStep(self.defaultStepIndex)

    # logic

    def loadEDL(self):
        assert self.movieFileName
        self.edlFileName = os.path.splitext(self.movieFileName)[0] + ".edl"
        if os.path.exists(self.edlFileName):
            self.edl = pyedl.load(open(self.edlFileName))
        else:
            self.edl = pyedl.EDL()
        self.edlDirty = False
        self.ui.edlWidget.setEDL(self.edl, self.mediaObject.duration())
        self.ui.actionSaveEDL.setEnabled(True)
        self.ui.actionStartCut.setEnabled(True)
        self.ui.actionStopCut.setEnabled(True)
        self.ui.actionDeleteCut.setEnabled(True)
        self.refreshTitle()

    def saveEDL(self):
        assert self.edlFileName
        assert self.edl is not None
        self.edl.normalize(timedelta(milliseconds=self.mediaObject.duration()))
        pyedl.dump(self.edl, open(self.edlFileName, "w"))
        self.edlChanged(dirty=False)

    def closeEDL(self):
        self.ui.actionPreviousCutBoundary.setEnabled(False)
        self.ui.actionNextCutBoundary.setEnabled(False)
        self.edlFileName = None
        self.edl = None
        self.edlDirty = False
        self.ui.edlWidget.resetEDL()
        self.ui.actionSaveEDL.setEnabled(False)
        self.ui.actionStartCut.setEnabled(False)
        self.ui.actionStopCut.setEnabled(False)
        self.ui.actionDeleteCut.setEnabled(False)
        self.refreshTitle()

    def play(self):
        if not self.mediaObject.state() == QMediaPlayer.PlayingState:
            self.mediaObject.play()
            self.ui.actionPlayPause.setChecked(True)

    def pause(self):
        if not self.mediaObject.state() == QMediaPlayer.PausedState:
            self.mediaObject.pause()
            self.ui.actionPlayPause.setChecked(False)
            self.tick()

    def getStep(self):
        stepIndex = self.ui.stepCombobox.currentIndex()
        return self.steps[stepIndex][0]

    def setStep(self, stepIndex):
        stepIndex = max(stepIndex, 0)
        stepIndex = min(stepIndex, len(self.steps)-1)
        self.ui.stepCombobox.setCurrentIndex(stepIndex)
        self.ui.actionDecreaseStep.setEnabled(stepIndex != 0)
        self.ui.actionIncreaseStep.setEnabled(stepIndex != len(self.steps)-1)

    def stepDown(self):
        stepIndex = self.ui.stepCombobox.currentIndex()
        self.setStep(stepIndex - 1)

    def stepUp(self):
        stepIndex = self.ui.stepCombobox.currentIndex()
        self.setStep(stepIndex + 1)

    def loadMovie(self, fileName):
        self.closeEDL()
        self.loading = True
        self.movieFileName = fileName
        absolute = QtCore.QFileInfo(self.movieFileName).absoluteFilePath()
        self.mediaObject.setMedia(QMediaContent(QtCore.QUrl.fromLocalFile(absolute)))

    def seekTo(self, pos):
        if pos < 0:
            pos = self.mediaObject.duration() - pos
        pos = max(pos, 0)
        pos = min(pos, self.mediaObject.duration())
        if pos > self.mediaObject.duration() - 500:
            self.pause()
        self.mediaObject.setPosition(pos)
        if not self.mediaObject.state() == QMediaPlayer.PlayingState:
            self.tick()

    def seekStep(self, step):
        pos = self.mediaObject.position() + step
        self.seekTo(pos)

    def edlChanged(self, dirty):
        self.edlDirty = dirty
        self.ui.edlWidget.setEDL(self.edl, self.mediaObject.duration())
        self.refreshTitle()

    def refreshTitle(self):
        if self.edlFileName:
            if self.edlDirty:
                star = "*"
            else:
                star = ""
            head, tail = os.path.split(os.path.abspath(self.edlFileName))
            self.setWindowTitle("%s%s (%s) - edledit" % (star, tail, head))
        else:
            self.setWindowTitle("edledit")

    # slots

    def closeEvent(self, event):
        if self.askSave():
            event.accept()
        else:
            event.ignore()

    def askSave(self):
        """ If needed, ask the user to save the current EDL

        return True is we can proceed, False is the user selected Cancel.
        """
        if not self.edlDirty:
            return True
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setText(tr("The current EDL has been modified."))
        msgBox.setInformativeText(tr("Do you want to save your changes?"))
        msgBox.setStandardButtons(
            QMessageBox.Save |
            QMessageBox.Discard | QMessageBox.Cancel)
        msgBox.setDefaultButton(QMessageBox.Save)
        ret = msgBox.exec_()
        if ret == QMessageBox.Save:
            self.saveEDL()
            return True
        elif ret == QMessageBox.Discard:
            return True
        else:
            return False

    def stateChanged(self, state):
        if state == QMediaPlayer.PausedState:
            if self.loading:
                self.loading = False
                self.loadEDL()  # TODO quit if error while loading EDL

    def seekableChanged(self, state):
        self.ui.actionPlayPause.setEnabled(state)
        self.ui.actionNextCutBoundary.setEnabled(state)
        self.ui.actionPreviousCutBoundary.setEnabled(state)
        self.ui.actionSkipBackwards.setEnabled(state)
        self.ui.actionSkipForward.setEnabled(state)
        return

    def mediaStatusChanged(self, state):
        if state == QMediaPlayer.EndOfMedia:
            self.ui.actionPlayPause.setEnabled(False)
            self.mediaObject.setPosition(self.mediaObject.position())
            self.pause()
            return

        if state == QMediaPlayer.LoadedMedia:
            self.pause()
            return

    def playerError(self, error):
        # FormatError can be an unsupported subtitle track. Ignore.
        if error == QMediaPlayer.FormatError:
            print "QMultimedia:", self.mediaObject.errorString()
            return

        if self.loading:
            QMessageBox.critical(
                self,
                tr("Error loading movie file"),
                self.mediaObject.errorString())
            self.loading = False
            self.mediaObject.stop()

    def tick(self, timeMs=None):
        if timeMs is None:
            if self.mediaObject.isVideoAvailable():
                timeMs = self.mediaObject.position()
            else:
                timeMs = 0

        self.ui.timeEditCurrentTime.setTime(QtCore.QTime(0, 0).addMSecs(timeMs))
        self.ui.edlWidget.tick(timeMs)
        if self.edl:
            block = self.edl.findBlock(ms2timedelta(timeMs))
        else:
            block = None
        if block:
            self.ui.actionDeleteCut.setEnabled(True)
            self.ui.actionCutSetActionSkip.setEnabled(
                block.action != pyedl.ACTION_SKIP)
            self.ui.actionCutSetActionMute.setEnabled(
                block.action != pyedl.ACTION_MUTE)
        else:
            self.ui.actionDeleteCut.setEnabled(False)
            self.ui.actionCutSetActionSkip.setEnabled(False)
            self.ui.actionCutSetActionMute.setEnabled(False)

        endOfMedia = timeMs == self.mediaObject.duration()
        self.ui.actionPlayPause.setEnabled(not endOfMedia)

    def smartSeekBackwards(self):
        self.stepDown()
        if self.getStep() <= 5000:
            self.pause()
        self.seekStep(-self.getStep())

    def smartSeekForward(self):
        self.stepDown()
        if self.getStep() <= 5000:
            self.pause()
        self.seekStep(self.getStep())

    def seekForward(self):
        self.seekStep(self.getStep())

    def seekBackwards(self):
        self.seekStep(-self.getStep())

    def seekNextBoundary(self):
        # self.pause()
        t = ms2timedelta(self.mediaObject.position())
        t = self.edl.getNextBoundary(t)
        if t:
            self.seekTo(timedelta2ms(t))
        else:
            self.seekTo(self.mediaObject.duration())

    def seekPrevBoundary(self):
        # self.pause()
        t = ms2timedelta(self.mediaObject.position())
        t = self.edl.getPrevBoundary(t)
        if t:
            self.seekTo(timedelta2ms(t))
        else:
            self.seekTo(0)

    def togglePlayPause(self):
        if not self.mediaObject.state() == QMediaPlayer.PlayingState:
            self.play()
        else:
            self.pause()

    def cutStart(self):
        t = timedelta(milliseconds=self.mediaObject.position())
        self.edl.cutStart(t)
        self.edlChanged(dirty=True)
        self.tick()

    def cutStop(self):
        t = timedelta(milliseconds=self.mediaObject.position())
        self.edl.cutStop(t)
        self.edlChanged(dirty=True)
        self.tick()

    def cutDelete(self):
        t = timedelta(milliseconds=self.mediaObject.position())
        self.edl.deleteBlock(t)
        self.edlChanged(dirty=True)
        self.tick()

    def cutSetAction(self, action):
        block = self.edl.findBlock(ms2timedelta(self.mediaObject.position()))
        if block is not None:
            block.action = action
            self.edlChanged(dirty=True)
        self.tick()

    def cutSetActionSkip(self):
        self.cutSetAction(pyedl.ACTION_SKIP)

    def cutSetActionMute(self):
        self.cutSetAction(pyedl.ACTION_MUTE)

    def actionFileOpen(self):
        if not self.askSave():
            return
        # get video file extensions from mime types database
        exts = ["*" + ext for (ext, mt) in mimetypes.types_map.items()
                if mt.startswith("video/")]
        exts = " ".join(exts)
        lastFolder = self.settings.value("last-folder", ".")
        fileName, selectedFilter = QFileDialog.getOpenFileName(
            self, tr("Select movie file to open"), lastFolder,
            tr("All Movie Files (%s);;All Files (*)") % exts)
        if fileName:
            # save directory so next getOpenFileName will be in same dir
            self.settings.setValue("last-folder", os.path.split(fileName)[0])
            self.loadMovie(fileName)

    def actionFileSaveEDL(self):
        self.saveEDL()

    def actionHelpAbout(self):
        AboutDialog(self).exec_()


class AboutDialog(QDialog):

    def __init__(self, *args, **kwargs):
        QDialog.__init__(self, *args, **kwargs)
        self.ui = Ui_AboutDialog()
        self.ui.setupUi(self)
        self.ui.labelNameVersion.setText("edledit %s" % __version__)

    def license(self):
        dlg = QDialog(self)
        ui = Ui_LicenseDialog()
        ui.setupUi(dlg)
        dlg.exec_()


def run():
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("edledit")

    # initialize QT translations
    qtTranslator = QtCore.QTranslator()
    qtTranslator.load(
        "qt_" + QtCore.QLocale.system().name(),
        QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.TranslationsPath))
    app.installTranslator(qtTranslator)
    # initialize edledit translations from resource file
    edleditTranslator = QtCore.QTranslator()
    trPath = os.path.join(
        os.path.dirname(__file__),
        "translations", "edledit_")
    trPath = trPath + QtCore.QLocale.system().name()
    edleditTranslator.load(trPath)
    app.installTranslator(edleditTranslator)

    mainWindow = MainWindow()
    mainWindow.show()
    if len(sys.argv) == 2:
        fileName = sys.argv[1].decode(sys.getfilesystemencoding())
        mainWindow.loadMovie(fileName)

    sys.exit(app.exec_())

if __name__ == "__main__":
    run()
