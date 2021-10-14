from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFile,
    QgsProcessingParameterDefinition,
    QgsProcessingContext,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterFeatureSink,
    QgsVectorLayer,
)
import processing
import csv
from pathlib import Path
import shutil

COEFFICIENTS_PATH = r"C:\Projects\work\nspect\QNSPECT\resources\coefficients\{0}.csv"


class CreateLookupTableTemplate(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterEnum(
                "LandCoverType",
                "Land Cover Type",
                options=["NLCD", "CCAP"],
                allowMultiple=False,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                "OutputCSV",
                "Output CSV",
                optional=False,
                fileFilter="CSV files (*.csv)",
                createByDefault=True,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "OpenOutputFile",
                "Open output file after running algorithm",
                defaultValue=True,
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(3, model_feedback)
        results = {}
        outputs = {}

        # Check if the output file is a CSV
        destination = self.parameterAsString(parameters, "OutputCSV", context)
        if not destination.lower().endswith(".csv"):
            feedback.reportError("Output file must be a CSV.", True)
            return {}

        # Find the template based on the land cover values chosen
        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        land_cover = self.parameterAsInt(parameters, "LandCoverType", context)
        if land_cover == 0:
            layer_name = "NCLD"
        elif land_cover == 1:
            layer_name = "CCAP"

        template_path = COEFFICIENTS_PATH.format(layer_name)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}
        shutil.copyfile(template_path, destination)
        outputs["CSV"] = destination

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}
        add_layer = self.parameterAsBool(parameters, "OpenOutputFile", context)
        if add_layer:
            context.addLayerToLoadOnCompletion(
                destination,
                QgsProcessingContext.LayerDetails(
                    layer_name, context.project(), layer_name
                ),
            )

        return results

    def name(self):
        return "Create Lookup Table Template"

    def displayName(self):
        return "Create Lookup Table Template"

    def group(self):
        return ""

    def groupId(self):
        return ""

    def createInstance(self):
        return CreateLookupTableTemplate()
