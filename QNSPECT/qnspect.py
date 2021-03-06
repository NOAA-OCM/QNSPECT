# -*- coding: utf-8 -*-

"""
/***************************************************************************
 QNSPECT
                                 A QGIS plugin
 QGIS Plugin for NOAA Nonpoint Source Pollution and Erosion Comparison Tool (NSPECT)
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-12-29
        copyright            : (C) 2021 by NOAA
        email                : ocm dot nspect dot admins at noaa dot gov
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = "Abdul Raheem Siddiqui"
__date__ = "2021-12-29"
__copyright__ = "(C) 2021 by NOAA"

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"

import os
import sys
import inspect

from qgis.core import QgsProcessingAlgorithm, QgsApplication

from QNSPECT.processing import QNSPECTProvider

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)


class QNSPECTPlugin(object):
    def __init__(self, iface):
        self.provider = None
        self.iface = iface

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = QNSPECTProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
