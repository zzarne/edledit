# This file is part of edledit.
# Copyright (C) 2010 Stephane Bidoul
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

# the only purpose of this file is to compensate for the lack
# of Phonon widgets in Qt Designer as installed on Ubuntu 10.10

from PyQt5.QtMultimediaWidgets import QVideoWidget

class VideoPlayer(QVideoWidget):
    pass

