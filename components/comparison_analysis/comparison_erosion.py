from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterFolderDestination
import processing
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent))
from comparison_utils import run_direct_and_percent_comparisons


def type_in_dir(scenario_dir: Path, compare_type: str) -> bool:
    compare_lower = compare_type.lower()
    for file in scenario_dir.iterdir():
        if file.suffix.lower() == ".tif":
            if compare_lower in file.stem.lower():
                return True
    return False


class ComparisonErosion(QgsProcessingAlgorithm):
    scenarioA = "ScenarioA"
    scenarioB = "ScenarioB"
    compareLocal = "Local"
    compareAccumulate = "Accumulated"
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

        feedback.pushInfo("Comparing outputs...")
        self.compare_outputs(
            parameters=parameters,
            feedback=feedback,
            context=context,
            outputs=outputs,
            compare_type=self.compareLocal,
            scenario_dir_a=scenario_dir_a,
            scenario_dir_b=scenario_dir_b,
            output_dir=output_dir,
        )
        self.compare_outputs(
            parameters=parameters,
            feedback=feedback,
            context=context,
            outputs=outputs,
            compare_type=self.compareAccumulate,
            scenario_dir_a=scenario_dir_a,
            scenario_dir_b=scenario_dir_b,
            output_dir=output_dir,
        )

        return results

    def name(self):
        return "Comparison Analysis (Erosion)"

    def displayName(self):
        return "Comparison Analysis (Erosion)"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return ComparisonErosion()

    def compare_outputs(
        self,
        parameters,
        feedback,
        context,
        outputs,
        compare_type: str,
        scenario_dir_a: Path,
        scenario_dir_b: Path,
        output_dir: Path,
    ):
        if self.parameterAsBool(parameters, compare_type, context):
            raster_a = type_in_dir(scenario_dir_a, compare_type)
            raster_b = type_in_dir(scenario_dir_b, compare_type)
            if raster_a and raster_b:
                run_direct_and_percent_comparisons(
                    scenario_dir_a=scenario_dir_a,
                    scenario_dir_b=scenario_dir_b,
                    output_dir=output_dir,
                    name=f"Erosion {compare_type}",
                    feedback=feedback,
                    context=context,
                    outputs=outputs,
                )
            else:
                feedback.pushWarning(
                    f"Comparison type {compare_type} was selected but one or more scenarios does not contain a related file."
                )
