# -*- coding: utf-8 -*-

"""
/***************************************************************************
 QNSPECT
                                 A QGIS plugin
 QGIS Plugin for NOAA Nonpoint Source Pollution and Erosion Comparison Tool (NSPECT)
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-04-27
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

__author__ = "NOAA"
__date__ = "2022-04-27"
__copyright__ = "(C) 2021 by NOAA"

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"


from QNSPECT.processing.qnspect_algorithm import QNSPECTAlgorithm
from QNSPECT.processing.algorithms.qnspect_utils import select_group, create_group


class QNSPECTCompareAlgorithm(QNSPECTAlgorithm):
    scenarioA = "ScenarioA"
    scenarioB = "ScenarioB"
    compareLocal = "Local"
    compareAccumulate = "Accumulated"
    loadOutputs = "LoadOutputs"
    outputDir = "Output"

    def __init__(self):
        super().__init__()
        self.name = ""
        self.load_outputs = False

    def postProcessAlgorithm(self, context, feedback):
        if self.load_outputs:
            project = context.project()
            root = project.instance().layerTreeRoot()  # get base level node

            create_group(self.name, root)
            select_group(self.name)  # so that layers are spit out within group

        return {}

    def group(self):
        return "Comparison"

    def groupId(self):
        return "comparison"
