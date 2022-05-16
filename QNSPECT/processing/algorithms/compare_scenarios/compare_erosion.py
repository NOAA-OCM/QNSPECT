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

__author__ = "Ian Todd"
__date__ = "2021-12-29"
__copyright__ = "(C) 2021 by NOAA"

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"

from pathlib import Path

from qgis.core import (
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFolderDestination,
    QgsProcessingException,
)
import processing

from QNSPECT.processing.algorithms.compare_scenarios.comparison_utils import run_direct_and_percent_comparisons
from QNSPECT.processing.algorithms.compare_scenarios.qnspect_compare_algorithm import QNSPECTCompareAlgorithm


class CompareErosion(QNSPECTCompareAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.scenarioA,
                "Scenario A Folder",
                behavior=QgsProcessingParameterFile.Folder,
                fileFilter="All files (*.*)",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.scenarioB,
                "Scenario B Folder",
                behavior=QgsProcessingParameterFile.Folder,
                fileFilter="All files (*.*)",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.compareLocal, "Compare Local Outputs", defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.compareAccumulate,
                "Compare Accumulated Outputs",
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.loadOutputs,
                "Open output files after running algorithm",
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.outputDir,
                "Output Folder",
                createByDefault=True,
                defaultValue=None,
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        results = {}
        outputs = {}

        self.scenario_dir_a = Path(
            self.parameterAsString(parameters, self.scenarioA, context)
        )
        self.scenario_dir_b = Path(
            self.parameterAsString(parameters, self.scenarioB, context)
        )
        self.name = f"{self.scenario_dir_a.name} vs {self.scenario_dir_b.name}"
        self.load_outputs = self.parameterAsBool(parameters, self.loadOutputs, context)

        self.output_dir = Path(
            self.parameterAsString(parameters, self.outputDir, context)
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        compare_local = self.parameterAsBool(parameters, self.compareLocal, context)
        compare_acc = self.parameterAsBool(parameters, self.compareAccumulate, context)
        if not any([compare_local, compare_acc]):
            raise QgsProcessingException(
                "Neither local nor accumulated outputs were selected."
            )

        feedback = QgsProcessingMultiStepFeedback(
            int(compare_local) + int(compare_acc), model_feedback
        )

        current_step = 1
        feedback.pushInfo("Comparing outputs...")
        if compare_local:
            feedback.setCurrentStep(current_step)
            current_step += 1
            if feedback.isCanceled():
                return {}
            self.compare_outputs(
                feedback=feedback,
                context=context,
                outputs=outputs,
                compare_type=self.compareLocal,
            )
        if compare_acc:
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            self.compare_outputs(
                feedback=feedback,
                context=context,
                outputs=outputs,
                compare_type=self.compareAccumulate,
            )

        return results

    def name(self):
        return "compare_scenarios_erosion"

    def displayName(self):
        return self.tr("Compare Scenarios (Erosion)")

    def group(self):
        return "Comparison"

    def groupId(self):
        return "comparison"

    def createInstance(self):
        return CompareErosion()

    def compare_outputs(
        self,
        feedback,
        context,
        outputs,
        compare_type: str,
    ):
        compare_name = f"Sediment {compare_type}"
        raster_a = (self.scenario_dir_a / f"{compare_name}.tif").is_file()
        raster_b = (self.scenario_dir_b / f"{compare_name}.tif").is_file()
        if raster_a and raster_b:
            run_direct_and_percent_comparisons(
                scenario_dir_a=self.scenario_dir_a,
                scenario_dir_b=self.scenario_dir_b,
                output_dir=self.output_dir,
                name=compare_name,
                feedback=feedback,
                context=context,
                outputs=outputs,
                load_outputs=self.load_outputs,
            )
        else:
            feedback.pushWarning(
                f"Comparison type {compare_type} was selected but one or more scenarios do not contain a related file."
            )

    def shortHelpString(self):
        return """<html><body>
<a href="https://www.noaa.gov/">Documentation</a>

<h2>Algorithm Description</h2>

<p>The `Compare Scenarios (Erosion)` algorithm calculates differences between the outputs of two `Run Erosion Analysis` scenarios. The user provides the location of the folders where the output of the scenario runs were saved. The user also needs to select the types of outputs they would like to compare.

The outputs of this algorithm are rasters that show the absolute and relative magnitude of the difference between the output of the provided two scenarios.</p>

<h2>Input Parameters</h2>

<h3>Scenario A Folder</h3>
<p>Folder location of the first scenario.</p>

<h3>Scenario B Folder</h3>
<p>Folder location of the second scenario.</p>

<h3>Compare Local Outputs</h3>
<p>Select to run the comparison on the local sediment outputs.</p>

<h3>Compare Accumulated Outputs</h3>
<p>Select to run on the comparison on the accumulated sediment outputs.</p>

<h2>Outputs</h2>

<h3>Output Folder</h3>
<p>The folder the results of the comparison will be saved to.</p>

</body></html>"""
