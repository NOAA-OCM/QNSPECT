from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterMatrix
from qgis.core import QgsProcessingParameterFolderDestination
import processing
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent))
from comparison_utils import run_direct_and_percent_comparisons
from qnspect_utils import filter_matrix


def find_all_matching(
    scenario_dir_a: Path, scenario_dir_b: Path, comparison_types: list
) -> list:
    scenario_a_stems = retrieve_scenario_file_stems(scenario_dir_a, comparison_types)
    scenario_b_stems = retrieve_scenario_file_stems(scenario_dir_b, comparison_types)
    return [stem for stem in scenario_a_stems if stem in scenario_b_stems]


def retrieve_scenario_file_stems(scenario_dir: Path, comparison_types: list) -> list:
    stems = []
    for file in scenario_dir.iterdir():
        if file.suffix == ".tif":
            for type in comparison_types:
                if type in file.stem:
                    stems.append(file.stem)
    return stems


class ComparisonPollution(QgsProcessingAlgorithm):
    scenarioA = "ScenarioA"
    scenarioB = "ScenarioB"
    compareLocal = "Local"
    compareAccumulate = "Accumulated"
    compareConcentration = "Concentration"
    compareGrid = "Grid"
    outputDir = "Output"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.scenarioA,
                "Scenario A",
                behavior=QgsProcessingParameterFile.Folder,
                fileFilter="All files (*.*)",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.scenarioB,
                "Scenario B",
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
                "Desired Outputs",
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
        output_dir = Path(self.parameterAsString(parameters, self.outputDir, context))
        output_dir.mkdir(parents=True, exist_ok=True)

        feedback.pushInfo("Starting getting comp types...")
        # Create a list of what will be compared
        comparison_types = []
        if self.parameterAsBool(parameters, self.compareLocal, context):
            comparison_types.append(self.compareLocal)
        if self.parameterAsBool(parameters, self.compareAccumulate, context):
            comparison_types.append(self.compareAccumulate)
        if self.parameterAsBool(parameters, self.compareConcentration, context):
            comparison_types.append(self.compareConcentration)
        if not comparison_types:
            feedback.reportError("No comparison types were checked.")
            return {}

        feedback.pushInfo("Filtering matrix...")
        pollutants = filter_matrix(
            self.parameterAsMatrix(parameters, self.compareGrid, context)
        )
        if "everything" in [pol.lower() for pol in pollutants]:
            feedback.pushInfo("Running everything...")
            matching_names = find_all_matching(
                scenario_dir_a, scenario_dir_b, comparison_types
            )
            for name in matching_names:
                run_direct_and_percent_comparisons(
                    scenario_dir_a=scenario_dir_a,
                    scenario_dir_b=scenario_dir_b,
                    output_dir=output_dir,
                    name=name,
                    feedback=feedback,
                    context=context,
                    outputs=outputs,
                )
        else:
            scenario_a_names = retrieve_scenario_file_stems(
                scenario_dir_a, comparison_types
            )
            scenario_b_names = retrieve_scenario_file_stems(
                scenario_dir_b, comparison_types
            )
            for pollutant in pollutants:
                for comp_type in comparison_types:
                    name = f"{pollutant} {comp_type}"
                    if name not in scenario_a_names:
                        feedback.pushWarning(
                            f'Tif for "{name}" was not found in Scenario A.'
                        )
                        continue
                    if name not in scenario_b_names:
                        feedback.pushWarning(
                            f'Tif for "{name}" was not found in Scenario B.'
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
                    )

        return results

    def name(self):
        return "Comparison Analysis (Pollution)"

    def displayName(self):
        return "Comparison Analysis (Pollution)"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return ComparisonPollution()
