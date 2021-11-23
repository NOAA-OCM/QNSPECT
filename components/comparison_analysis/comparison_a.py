"""
Model exported as python.
Name : model
Group : 
With QGIS : 31610
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile, QgsProcessingParameterMatrix
from qgis.core import QgsProcessingParameterBoolean
import processing


class CompAnalA(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        default_table = ["Local", "Y", "Concentration", "N", "Accumulated", "N"]

        self.addParameter(
            QgsProcessingParameterFile(
                "AnalysisA",
                "Analysis A",
                behavior=QgsProcessingParameterFile.File,
                fileFilter="JSON Files (*.json)",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                "AnalysisB",
                "Analysis B",
                behavior=QgsProcessingParameterFile.File,
                fileFilter="JSON Files (*.json)",
                defaultValue=None,
            )
        )

        self.addParameter(
            QgsProcessingParameterMatrix(
                "Runoff",
                "Runoff",
                optional=True,
                headers=["Type", "Output? [Y/N]"],
                defaultValue=default_table,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                "Lead",
                "Lead",
                optional=True,
                headers=["Type", "Output? [Y/N]"],
                defaultValue=default_table,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                "Nitrogen",
                "Nitrogen",
                optional=True,
                headers=["Type", "Output? [Y/N]"],
                defaultValue=default_table,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                "Phosphorus",
                "Phosphorus",
                optional=True,
                headers=["Type", "Output? [Y/N]"],
                defaultValue=default_table,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                "Zinc",
                "Zinc",
                optional=True,
                headers=["Type", "Output? [Y/N]"],
                defaultValue=default_table,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                "TSS",
                "TSS",
                optional=True,
                headers=["Type", "Output? [Y/N]"],
                defaultValue=default_table,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                "Other",
                "Other",
                optional=True,
                headers=["Type", "Output? [Y/N]"],
                defaultValue=default_table,
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
        return "Comparison Analysis (JSON Entry)"

    def displayName(self):
        return "Comparison Analysis (JSON Entry)"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return CompAnalA()
