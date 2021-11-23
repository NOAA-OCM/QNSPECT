"""
Model exported as python.
Name : model
Group : 
With QGIS : 31610
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterBoolean, QgsProcessingParameterEnum
import processing


class CompAnalA(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        options = [
            "Hawaii_NoChange",
            "Hawaii_GulfCourse",
            "Florida_NoChange",
            "Florida_GulfCourse",
        ]
        self.addParameter(
            QgsProcessingParameterEnum(
                "RasterA",
                "Analysis A",
                options=options,
                allowMultiple=False,
                defaultValue=[],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "AnalysisB",
                "Analysis B",
                options=options,
                allowMultiple=False,
                defaultValue=[],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "Type",
                "Analysis Type",
                options=["Pollution", "Erosion"],
                allowMultiple=False,
                defaultValue=[],
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean("Runoff", "Runoff", defaultValue=True)
        )
        self.addParameter(
            QgsProcessingParameterBoolean("Lead", "Lead", defaultValue=True)
        )
        self.addParameter(
            QgsProcessingParameterBoolean("Nitrogen", "Nitrogen", defaultValue=True)
        )
        self.addParameter(
            QgsProcessingParameterBoolean("Phosphorus", "Phosphorus", defaultValue=True)
        )
        self.addParameter(
            QgsProcessingParameterBoolean("Zinc", "Zinc", defaultValue=True)
        )
        self.addParameter(
            QgsProcessingParameterBoolean("TSS", "TSS", defaultValue=True)
        )
        self.addParameter(
            QgsProcessingParameterBoolean("Other", "Custom", defaultValue=False)
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        return results

    def name(self):
        return "Comparison Analysis (Database Entry"

    def displayName(self):
        return "Comparison Analysis (Database Entry)"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return CompAnalA()
