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
from pathlib import Path


class CreateLookupTableTemplate(QgsProcessingAlgorithm):
    landCoverIndex = "LandCoverType"
    landCoverParam = "LandCoverType"
    output = "OutputTable"

    def initAlgorithm(self, config=None):
        self.landCoverTypes = []
        for csvfile in self.coefficient_dir().iterdir():
            if csvfile.suffix.lower() == ".csv":
                self.landCoverTypes.append(csvfile.stem)

        self.addParameter(
            QgsProcessingParameterEnum(
                self.landCoverParam,
                "Land Cover Type",
                options=self.landCoverTypes,
                allowMultiple=False,
                defaultValue=0,
            )
        )

        try:  ## Account for changes in the constructor parameters between QGIS 3.x versions
            self.addParameter(
                QgsProcessingParameterFeatureSink(
                    self.output,
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
                    self.output,
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
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        index = self.parameterAsInt(parameters, self.landCoverIndex, context)
        land_cover = self.landCoverTypes[index]

        coef_dir = self.coefficient_dir()
        template_path = f"file:///{coef_dir / land_cover}.csv"
        template_layer = QgsVectorLayer(
            template_path, "template_layer", "delimitedtext"
        )

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        sink, dest_id = self.parameterAsSink(
            parameters, self.output, context, template_layer.fields()
        )
        for feature in template_layer.getFeatures():
            insert_feature = QgsFeature(feature)
            sink.addFeature(insert_feature, QgsFeatureSink.FastInsert)

        return {self.output: dest_id}

    def name(self):
        return "Create Lookup Table Template"

    def displayName(self):
        return "Create Lookup Table Template"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def shortHelpString(self):
        return """<html><body><h2>Algorithm description</h2>
<p>This algorithm creates a copy of the land characteristics packaged with QNSPECT. The spreadsheet output will have the necessary fields needed for running the pollution and erosion analysis tools. The intent of this tool is to create a copy that can be edited to include any custom land use types and coefficients necessary for your analysis.</p>
<h2>Input parameters</h2>
<h3>Land Cover Type</h3>
<p>The name of the land cover characteristics.</p>
<h2>Outputs</h2>
<h3>Output Table</h3>
<p>A copy of the default land characteristics in a spreadsheet format (CSV, Geopackage, etc.)</p>
<br></body></html>"""

    def createInstance(self):
        return CreateLookupTableTemplate()

    def coefficient_dir(self):
        root = Path(__file__).parent.parent.parent
        return root / "resources" / "coefficients"
