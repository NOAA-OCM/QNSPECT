# -*- coding: utf-8 -*-

"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Abdul Raheem Siddiqui'
__date__ = '2021-12-29'
__copyright__ = '(C) 2021 by NOAA'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import (
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFile,
    QgsProcessingException
)

import processing
import json

from QNSPECT.qnspect_algorithm import QNSPECTAlgorithm


class LoadPreviousRun(QNSPECTAlgorithm):
    load_parameters = {}
    alg = ""

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile('RunFile', 'Run File', behavior=QgsProcessingParameterFile.File, fileFilter='QNSPECT Files (*pol.json *ero.json)', defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        run_file = self.parameterAsString(parameters, "RunFile", context)
        if run_file.lower().endswith(".pol.json"):
            self.alg = "qnspect:run_pollution_analysis"
        elif run_file.lower().endswith(".ero.json"):
            self.alg = "qnspect:run_erosion_analysis" 
        else:
            raise QgsProcessingException("Wrong or missing parameter value: Run File")
            
        with open(run_file) as f:
            data = json.load(f)

        self.load_parameters = data["Inputs"]
        
        return results

    def postProcessAlgorithm(self, context, feedback):
        # this can be handled better through QGIS Tasks
        # https://www.opengis.ch/2016/09/07/using-threads-in-qgis-python-plugins/
        # https://www.opengis.ch/2018/06/22/threads-in-pyqgis3/
        processing.execAlgorithmDialog(self.alg, self.load_parameters)
        return {}

    def name(self):
        return 'load_previous_run'

    def displayName(self):
        return self.tr('Load Previous Run')

    def group(self):
        return self.tr('Analysis')

    def groupId(self):
        return 'analysis'

    def createInstance(self):
        return LoadPreviousRun()

    def shortHelpString(self):
        return '''<html><body>
<a href="https://www.noaa.gov/">Documentation</a>

<h2>Algorithm Description</h2>

<p>The `Load Previous Run` component uses a JSON file from a previous analysis run to load the `Run Pollution Analysis` or `Run Erosion Analysis` tool. This can be helpful when running multiple scenarios with only one or two parameters changed between them.

After running, the appropriate analysis component will load with the parameters of the previous scenario automatically populated.</p>

<h2>Input Parameters</h2>

<h3>Run File</h3>
<p>JSON file created by the `Run Pollution Analysis` or `Run Erosion Analysis` algorithms. The file must have the extension `.pol.json` for pollution analysis and `.ero.json` for erosion analysis.</p>

</body></html>'''