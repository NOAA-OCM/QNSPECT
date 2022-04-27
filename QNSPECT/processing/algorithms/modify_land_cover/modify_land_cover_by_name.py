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
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSource,
)
import processing

from QNSPECT.processing.qnspect_algorithm import QNSPECTAlgorithm


class ModifyLandCoverByName(QNSPECTAlgorithm):
    inputTable = "InputTable"
    inputVector = "InputVector"
    inputRaster = "InputRaster"
    output = "OutputRaster"
    landCover = "LandCover"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.inputTable,
                "Land Cover Lookup Table",
                types=[QgsProcessing.TypeVector],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.landCover,
                "Name of Land Cover to Apply",
                multiLine=False,
                defaultValue="",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.inputVector,
                "Areas to Modify",
                types=[QgsProcessing.TypeVectorPolygon],
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
        feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

        # Find the named values
        coefficient_name = self.parameterAsString(parameters, self.landCover, context)
        name_compare = coefficient_name.lower().replace(" ", "")
        table = self.parameterAsVectorLayer(parameters, self.inputTable, context)
        if "lc_name" not in table.fields().names():
            feedback.reportError('Field "lc_name" required for the coefficients table.')
            return {}
        if "lc_value" not in table.fields().names():
            feedback.reportError(
                'Field "lc_value" required for the coefficients table.'
            )
            return {}
        for feature in table.getFeatures():
            candidate = feature.attribute("lc_name").lower().replace(" ", "")
            if candidate == name_compare:
                lc_value = int(feature.attribute("lc_value"))
                break
        else:
            feedback.reportError(f"Unable to find {coefficient_name} in the table.")
            return {}

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

        # Rasterize (overwrite with fixed value)
        alg_params = {
            "ADD": False,
            "BURN": lc_value,
            "EXTRA":lc_value
            "INPUT": parameters[self.inputVector],
            "INPUT_RASTER": outputs["ClipRasterByExtent"]["OUTPUT"],
        }
        outputs["RasterizeOverwriteWithFixedValue"] = processing.run(
            "gdal:rasterize_over_fixed_value",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        return results

    def name(self):
        return "modify_land_cover_custom_lookup_table"

    def displayName(self):
        return self.tr("Modify Land Cover (Custom Lookup Table)")

    def group(self):
        return self.tr("Data Preparation")

    def groupId(self):
        return "data_preparation"

    def createInstance(self):
        return ModifyLandCoverByName()

    def shortHelpString(self):
        return """<html><body>
<a href="https://www.noaa.gov/">Documentation</a>

<h2>Algorithm Description</h2>

<p>The `Modify Land Cover (Custom Lookup Table)` algorithm changes a section of a raster based on the land cover name in a custom lookup table. 
This tool is designed to make it easy to change a raster's values in an area based on the name of the new land cover. 
The pixels of the input raster layer that overlap with the areas of the input vector layer will be changed to the land cover code of the name selected.</p>

<h2>Input Parameters</h2>

<h3>Land Cover Lookup Table</h3>
<p>The lookup table used to map the land cover name to a raster value. The lookup table must include the land cover name in a field called "lc_name" and a corresponding value in a field called "lc_value".</p>
lc_value
<h3>Name of Land Cover to Apply</h3>
<p>The name of the new land cover.</p>

<h3>Areas to Modify</h3>
<p>Polygon vector layer that overlaps the pixels that should be changed.</p>

<h3>Land Cover Raster</h3>
<p>Land cover raster that needs to be modified.</p>

<h2>Outputs</h2>

<h3>Modified Land Cover Raster</h3>
<p>The location the modified land cover raster will be saved to.</p>

</body></html>"""
