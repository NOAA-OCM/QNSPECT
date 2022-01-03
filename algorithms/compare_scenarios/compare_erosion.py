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

__author__ = 'Ian Todd'
__date__ = '2021-12-29'
__copyright__ = '(C) 2021 by NOAA'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'


from qgis.core import (
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFolderDestination,
    QgsProcessingException
)

import processing
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent))
from comparison_utils import run_direct_and_percent_comparisons

from QNSPECT.qnspect_algorithm import QNSPECTAlgorithm


class CompareErosion(QNSPECTAlgorithm):
    scenarioA = "ScenarioA"
    scenarioB = "ScenarioB"
    compareLocal = "Local"
    compareAccumulate = "Accumulated"
    loadOutputs = "LoadOutputs"
    outputDir = "Output"

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
                "Output Directory",
                createByDefault=True,
                defaultValue=None,
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        scenario_dir_a = Path(
            self.parameterAsString(parameters, self.scenarioA, context)
        )
        scenario_dir_b = Path(
            self.parameterAsString(parameters, self.scenarioB, context)
        )
        load_outputs = self.parameterAsBool(parameters, self.loadOutputs, context)
        output_dir = Path(self.parameterAsString(parameters, self.outputDir, context))
        output_dir.mkdir(parents=True, exist_ok=True)

        compare_local = self.parameterAsBool(parameters, self.compareLocal, context)
        compare_acc = self.parameterAsBool(parameters, self.compareAccumulate, context)
        if not any([compare_local, compare_acc]):
            raise QgsProcessingException("Neither local nor accumulated outputs were selected.")

        feedback.pushInfo("Comparing outputs...")
        if compare_local:
            self.compare_outputs(
                feedback=feedback,
                context=context,
                outputs=outputs,
                compare_type=self.compareLocal,
                scenario_dir_a=scenario_dir_a,
                scenario_dir_b=scenario_dir_b,
                output_dir=output_dir,
                load_outputs=load_outputs,
            )
        if compare_acc:
            self.compare_outputs(
                feedback=feedback,
                context=context,
                outputs=outputs,
                compare_type=self.compareAccumulate,
                scenario_dir_a=scenario_dir_a,
                scenario_dir_b=scenario_dir_b,
                output_dir=output_dir,
                load_outputs=load_outputs,
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
        scenario_dir_a: Path,
        scenario_dir_b: Path,
        output_dir: Path,
        load_outputs: bool,
    ):
        compare_name = f"Erosion {compare_type}"
        raster_a = (scenario_dir_a / f"{compare_name}.tif").is_file()
        raster_b = (scenario_dir_b / f"{compare_name}.tif").is_file()
        if raster_a and raster_b:
            run_direct_and_percent_comparisons(
                scenario_dir_a=scenario_dir_a,
                scenario_dir_b=scenario_dir_b,
                output_dir=output_dir,
                name=compare_name,
                feedback=feedback,
                context=context,
                outputs=outputs,
                load_outputs=load_outputs,
            )
        else:
            feedback.pushWarning(
                f"Comparison type {compare_type} was selected but one or more scenarios do not contain a related file."
            )