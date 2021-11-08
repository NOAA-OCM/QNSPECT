from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterEnum,
    QgsVectorLayer,
    QgsProcessingParameterFeatureSink,
    QgsVectorFileWriter,
    QgsFeatureSink,
    QgsFeature,
)
import processing
import os

COEFFICIENTS_PATH = (
    r"file:///C:\Projects\work\nspect\QNSPECT\resources\coefficients\{0}.csv"
)


class CreateLookupTableTemplate(QgsProcessingAlgorithm):
    outputTable = "OutputTable"
    landCoverIndex = "LandCoverType"
    landCoverTypes = ["NLCD", "CCAP"]

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterEnum(
                self.landCoverIndex,
                "Land Cover Type",
                options=self.landCoverTypes,
                allowMultiple=False,
                defaultValue=0,
            )
        )

        try:  ## Account for changes in the constructor parameters between QGIS 3.x versions
            self.addParameter(
                QgsProcessingParameterFeatureSink(
                    self.outputTable,
                    "Output Table",
                    type=QgsProcessing.TypeVector,
                    createByDefault=True,
                    supportsAppend=True,
                    defaultValue=None,
                )
            )
        except TypeError:
            self.addParameter(
                QgsProcessingParameterFeatureSink(
                    self.outputTable,
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

        index = self.parameterAsInt(parameters, self.landCoverIndex, context)
        land_cover = self.landCoverTypes[index]

        template_path = COEFFICIENTS_PATH.format(land_cover)
        template_layer = QgsVectorLayer(
            template_path, "template_layer", "delimitedtext"
        )

        sink, dest_id = self.parameterAsSink(
            parameters, self.outputTable, context, template_layer.fields()
        )
        for feature in template_layer.getFeatures():
            insert_feature = QgsFeature(feature)
            sink.addFeature(insert_feature, QgsFeatureSink.FastInsert)

        return {self.outputTable: dest_id}

    def name(self):
        return "Create Lookup Table Template"

    def displayName(self):
        return "Create Lookup Table Template"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return CreateLookupTableTemplate()
