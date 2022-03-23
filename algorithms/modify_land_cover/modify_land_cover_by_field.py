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

__author__ = 'Ian Todd'
__date__ = '2021-12-29'
__copyright__ = '(C) 2021 by NOAA'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'


from qgis.core import (QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterRasterDestination
)
import processing

from QNSPECT.qnspect_algorithm import QNSPECTAlgorithm

class ModifyLandCover(QNSPECTAlgorithm):
    inputVector = "InputVector"
    field = "Field"
    inputRaster = "InputRaster"
    output = "OutputRaster"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.inputVector,
                "Areas to Modify",
                types=[QgsProcessing.TypeVectorPolygon],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.field,
                "Land Cover Value Field",
                optional=True,
                type=QgsProcessingParameterField.Numeric,
                parentLayerParameterName=self.inputVector,
                allowMultiple=False,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.inputRaster, "Land Cover Raster", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.output,
                "Modified Land Cover Raster",
                createByDefault=True,
                defaultValue=None,
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        # Rasterize with overwrite was the best method for accomplishing this. Since it directly changes the input, the original needs to be copied prior to execution
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        # Uses clip raster to get a copy of the original raster
        # Some other method of copying in a way that allows for temporary output would be better for this part
        alg_params = {
            "DATA_TYPE": 0,
            "EXTRA": "",
            "INPUT": parameters[self.inputRaster],
            "NODATA": None,
            "OPTIONS": "",
            "PROJWIN": parameters[self.inputRaster],
            "OUTPUT": parameters[self.output],
        }
        outputs["ClipRasterByExtent"] = processing.run(
            "gdal:cliprasterbyextent",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Rasterize (overwrite with attribute)
        alg_params = {
            "ADD": False,
            "EXTRA": "",
            "FIELD": parameters[self.field],
            "INPUT": parameters[self.inputVector],
            "INPUT_RASTER": outputs["ClipRasterByExtent"]["OUTPUT"],
        }
        outputs["RasterizeOverwriteWithAttribute"] = processing.run(
            "gdal:rasterize_over",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )

        return results

    def name(self):
        return "modify_land_cover_vector_field"

    def displayName(self):
        return self.tr("Modify Land Cover (Vector Field)")

    def group(self):
        return self.tr("Data Preparation")

    def groupId(self):
        return "data_preparation"

    def createInstance(self):
        return ModifyLandCover()

    def shortHelpString(self):
        return """<html><body>
<a href="https://www.noaa.gov/">Documentation</a>

<h2>Algorithm Description</h2>

<p>The `Modify Land Cover (Vector Field)` algorithm changes a section of a raster based on the land cover numeric value in a polygon vector layer.
The pixels of the input raster layer that overlap with each polygon of the input vector layer will be changed to the land cover code of the polygon's land cover field.</p>

<h2>Input Parameters</h2>

<h3>Areas to Modify</h3>
<p>Polygon vector layer that overlaps the pixels that should be changed.</p>

<h3>Land Cover Value Field</h3>
<p>The field with the land cover value the raster pixels will be changed to. If this is left blank, the algorithm will try to use a field called "lu_value".</p>

<h3>Land Cover Raster</h3>
<p>Land cover raster that needs to be modified.</p>

<h2>Outputs</h2>

<h3>Modified Land Cover Raster</h3>
<p>The location the modified land cover raster will be saved to.</p>

</body></html>"""
