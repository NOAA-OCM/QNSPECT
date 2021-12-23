from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterMatrix
from qgis.core import QgsProcessingParameterFolderDestination
from qgis.core import QgsProcessingException
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


class ComparisonPollution(QgsProcessingAlgorithm):
    scenarioA = "ScenarioA"
    scenarioB = "ScenarioB"
    compareLocal = "Local"
    compareAccumulate = "Accumulated"
    compareConcentration = "Concentration"
    compareGrid = "Grid"
    outputDir = "Output"
    loadOutputs = "LoadOutputs"

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
            raise QgsProcessingException("No comparison types were checked.")

        feedback.pushInfo("Filtering matrix...")
        pollutants = filter_matrix(
            self.parameterAsMatrix(parameters, self.compareGrid, context)
        )
        if not pollutants:
            raise QgsProcessingException("No pollutants were selected in the 'Desired Outputs' parameter.")

        if "everything" in [pol.lower() for pol in pollutants]:
            feedback.pushInfo("Running everything...")
            matching_names = find_all_matching(
                scenario_dir_a, scenario_dir_b, comparison_types
            )
            if not matching_names:
                feedback.pushWarning(
                    "No valid comparisons were found between the two scenario folders."
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
                    load_outputs=load_outputs,
                )
        else:
            for pollutant in pollutants:
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
                        load_outputs=load_outputs,
                    )

        return results

    def name(self):
        return "Compare Scenarios (Pollution)"

    def displayName(self):
        return "Compare Scenarios (Pollution)"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return ComparisonPollution()
