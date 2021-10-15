from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsVectorLayer,
    QgsProcessingParameterFeatureSink,
    QgsVectorFileWriter,
)
import processing
import os

COEFFICIENTS_PATH = (
    r"file:///C:\Projects\work\nspect\QNSPECT\resources\coefficients\{0}.csv"
)


class CreateLookupTableTemplate(QgsProcessingAlgorithm):
    landCoverTypes = ["NLCD", "CCAP"]

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterEnum(
                "LandCoverType",
                "Land Cover Type",
                options=self.landCoverTypes,
                allowMultiple=False,
                defaultValue=0,
            )
        )

        try:
            self.addParameter(
                QgsProcessingParameterFeatureSink(
                    "OutputTable",
                    "Output Table",
                    type=QgsProcessing.TypeVector,
                    createByDefault=True,
                    supportsAppend=True,
                    defaultValue=None,
                )
            )
        except TypeError:  ## Account for changes in the constructor parameters between versions
            self.addParameter(
                QgsProcessingParameterFeatureSink(
                    "OutputTable",
                    "Output Table",
                    type=QgsProcessing.TypeVector,
                    defaultValue=None,
                    createByDefault=True,
                    optional=False,
                )
            )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(3, model_feedback)
        results = {}
        outputs = {}

        # Check if the output file is a CSV or GeoPackage
        destination = self.parameterDefinition("OutputTable").valueAsPythonString(
            parameters["OutputTable"], context
        )
        # QgsProcessing.TEMPORARY_OUTPUT
        feedback.reportError(str(destination))
        while destination.startswith("'") or destination.startswith('"'):
            destination = destination[1:]
        while destination.endswith("'") or destination.endswith('"'):
            destination = destination[:-1]
        try:
            extention = os.path.splitext(destination)[1].lower()
        except IndexError:
            extention = None
        if extention != ".csv":
            feedback.reportError("Output file must be a CSV.", True)
            return {}

        # Find the template based on the land cover values chosen
        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        land_cover = self.parameterAsInt(parameters, "LandCoverType", context)
        layer_name = self.landCoverTypes[land_cover]

        template_path = COEFFICIENTS_PATH.format(layer_name)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}
        table_layer = QgsVectorLayer(template_path, "scratch", "delimitedtext")

        error_code, error_message = outputs[
            "OutputTable"
        ] = QgsVectorFileWriter.writeAsVectorFormat(
            table_layer, destination, "utf-8", driverName="CSV"
        )
        if error_code != QgsVectorFileWriter.NoError:
            feedback.reportError(f"Error writing to output file: {error_message}")
            return {}

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
