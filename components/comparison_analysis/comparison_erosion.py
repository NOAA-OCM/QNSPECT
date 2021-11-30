from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterMatrix
from qgis.core import QgsProcessingParameterFolderDestination
import processing


class ComparisonErosion(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                "ScenarioA",
                "Scenario A",
                behavior=QgsProcessingParameterFile.File,
                fileFilter="Erosion Analyses (*.ero.json)",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                "ScenarioB",
                "Scenario B",
                behavior=QgsProcessingParameterFile.File,
                fileFilter="Erosion Analyses (*.ero.json)",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "Local", "Compare Local Outputs", defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "Accumulate", "Compare Accumulated Outputs", defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                "OutputDirectory",
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
