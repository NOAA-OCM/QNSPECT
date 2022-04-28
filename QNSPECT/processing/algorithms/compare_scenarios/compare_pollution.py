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


from qgis.core import (
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterMatrix,
    QgsProcessingParameterFolderDestination,
    QgsProcessingException,
)
import processing
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parents[1]))
from comparison_utils import run_direct_and_percent_comparisons
from qnspect_utils import filter_matrix
from qnspect_compare_algorithm import QNSPECTCompareAlgorithm


def find_all_matching(
    scenario_dir_a: Path, scenario_dir_b: Path, comparison_types: list
) -> list:
    """Finds all of the stems where valid comparison rasters exist in both folders."""
    matches = []
    scenario_a_stems = retrieve_scenario_file_stems(scenario_dir_a, comparison_types)
    for stem in scenario_a_stems:
        # Prevent finding comparison potentials between previous comparisons
        if len(stem.split(" ")) == 2:
            if (scenario_dir_a / f"{stem}.tif").is_file():
                if (scenario_dir_b / f"{stem}.tif").is_file():
                    matches.append(stem)
    return matches


def retrieve_scenario_file_stems(scenario_dir: Path, comparison_types: list) -> list:
    stems = []
    for file in scenario_dir.iterdir():
        if file.suffix == ".tif":
            for type in comparison_types:
                if type in file.stem:
                    stems.append(file.stem)
    return stems


class ComparePollution(QNSPECTCompareAlgorithm):
    compareConcentration = "Concentration"
    compareGrid = "Grid"

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
                self.compareConcentration,
                "Compare Concentration Outputs",
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                self.compareGrid,
                "Pollutant Outputs",
                optional=False,
                headers=["Name", "Output? [Y/N]"],
                defaultValue=[
                    "Everything",
                    "N",
                    "Runoff",
                    "N",
                    "Lead",
                    "N",
                    "Nitrogen",
                    "N",
                    "Phosphorus",
                    "N",
                    "Zinc",
                    "N",
                    "TSS",
                    "N",
                ],
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

        scenario_dir_a = Path(
            self.parameterAsString(parameters, self.scenarioA, context)
        )
        scenario_dir_b = Path(
            self.parameterAsString(parameters, self.scenarioB, context)
        )
        self.name = f"{scenario_dir_a.name} vs {scenario_dir_b.name}"
        self.load_outputs = self.parameterAsBool(parameters, self.loadOutputs, context)

        output_dir = Path(self.parameterAsString(parameters, self.outputDir, context))
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a list of what will be compared
        comparison_types = []
        if self.parameterAsBool(parameters, self.compareLocal, context):
            comparison_types.append(self.compareLocal)
        if self.parameterAsBool(parameters, self.compareAccumulate, context):
            comparison_types.append(self.compareAccumulate)
        if self.parameterAsBool(parameters, self.compareConcentration, context):
            comparison_types.append(self.compareConcentration)
        if not comparison_types:
            raise QgsProcessingException("No comparison types were checked.")

        pollutants = filter_matrix(
            self.parameterAsMatrix(parameters, self.compareGrid, context)
        )
        if not pollutants:
            raise QgsProcessingException(
                "No pollutants were selected in the 'Pollutant Outputs' parameter."
            )

        run_everything = "everything" in [pol.lower() for pol in pollutants]
        if run_everything:
            matching_names = find_all_matching(
                scenario_dir_a, scenario_dir_b, comparison_types
            )
            if not matching_names:
                raise QgsProcessingException(
                    "No valid comparisons were found between the two scenario folders."
                )
            total_steps = len(matching_names)
        else:
            total_steps = len(pollutants)
        feedback = QgsProcessingMultiStepFeedback(total_steps + 1, model_feedback)
        current_step = 1

        if run_everything:
            feedback.pushInfo("Running everything...")
            for name in matching_names:
                feedback.setCurrentStep(current_step)
                current_step += 1
                if feedback.isCanceled():
                    return {}
                run_direct_and_percent_comparisons(
                    scenario_dir_a=scenario_dir_a,
                    scenario_dir_b=scenario_dir_b,
                    output_dir=output_dir,
                    name=name,
                    feedback=feedback,
                    context=context,
                    outputs=outputs,
                    load_outputs=self.load_outputs,
                )
        else:
            for pollutant in pollutants:
                feedback.setCurrentStep(current_step)
                current_step += 1
                if feedback.isCanceled():
                    return {}
                for comp_type in comparison_types:
                    name = f"{pollutant} {comp_type}"

                    # Check for existence of both comparison types for the pollutant
                    pollutant_comp_a = (scenario_dir_a / f"{name}.tif").is_file()
                    pollutant_comp_b = (scenario_dir_b / f"{name}.tif").is_file()
                    if not (pollutant_comp_a and pollutant_comp_b):
                        if pollutant_comp_b:
                            feedback.pushWarning(
                                f'TIFF for "{name}" was not found in Scenario A.'
                            )
                        elif pollutant_comp_a:
                            feedback.pushWarning(
                                f'TIFF for "{name}" was not found in Scenario B.'
                            )
                        else:
                            feedback.pushWarning(
                                f'TIFF for "{name}" was not found in Scenarios A and B.'
                            )
                        continue

                    run_direct_and_percent_comparisons(
                        scenario_dir_a=scenario_dir_a,
                        scenario_dir_b=scenario_dir_b,
                        output_dir=output_dir,
                        name=name,
                        feedback=feedback,
                        context=context,
                        outputs=outputs,
                        load_outputs=self.load_outputs,
                    )

        return results

    def name(self):
        return "compare_scenarios_pollution"

    def displayName(self):
        return self.tr("Compare Scenarios (Pollution)")

    def createInstance(self):
        return ComparePollution()

    def shortHelpString(self):
        return """<html><body>
<a href="https://www.noaa.gov/">Documentation</a>

<h2>Algorithm Description</h2>

<p>The `Compare Scenarios (Pollution)` calculates differences between the outputs of two `Run Pollution Analysis` scenarios. The user provides the location of the folders where the output of the scenario runs were saved. The user also needs to provide the types of outputs they would like to compare.

The outputs of this algorithm are rasters that show the absolute and relative magnitude of the difference between the outputs of the provided two scenarios.</p>

<h2>Input Parameters</h2>

<h3>Scenario A Folder</h3>
<p>Folder location of the first scenario.</p>

<h3>Scenario B Folder</h3>
<p>Folder location of the second scenario.</p>

<h3>Compare Local Outputs</h3>
<p>Select to run the comparison on the local rasters.</p>

<h3>Compare Accumulated Outputs</h3>
<p>Select to run on the comparison on the accumulated rasters.</p>

<h3>Compare Concentration Outputs</h3>
<p>Select to run on the comparison on the concentration rasters.</p>

<h3>Pollutant Outputs</h3>
<p>The comparison will be run on runoff and pollutants with Y in the Output column. If `Everything` is marked as Y, the comparison will be run on all pollutants that are shared between the scenarios.

The user can add more pollutants to the table. To exclude an output from the analysis, write N in the Output column. You must click OK after editing to save your changes.</p>

<h2>Outputs</h2>

<h3>Output Folder</h3>
<p>The folder the results of the comparison will be saved to.</p>

</body></html>"""
