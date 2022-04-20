# -*- coding: utf-8 -*-

"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = "Ian Todd"
__date__ = "2021-12-29"
__copyright__ = "(C) 2021 by NOAA"

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"


from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterEnum,
    QgsVectorLayer,
    QgsProcessingParameterFeatureSink,
    QgsFeatureSink,
    QgsFeature,
)
import processing
import os
from pathlib import Path

from QNSPECT.qnspect_algorithm import QNSPECTAlgorithm


class CreateLookupTableTemplate(QNSPECTAlgorithm):
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
        return "create_lookup_table_template"

    def displayName(self):
        return self.tr("Create Lookup Table Template")

    def group(self):
        return self.tr("Data Preparation")

    def groupId(self):
        return "data_preparation"

    def shortHelpString(self):
        return """<html><body><h2>Algorithm description</h2>
<p>This algorithm creates a copy of the land characteristics packaged with QNSPECT. The spreadsheet output will have the necessary fields needed for running the pollution and erosion analysis tools. The intent of this tool is to create a copy that can be edited to include any custom land cover types and coefficients necessary for your analysis.</p>
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
