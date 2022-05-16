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

import csv
import processing
from typing import Dict
from pathlib import Path

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterFeatureSource,
)

from QNSPECT.processing.qnspect_algorithm import QNSPECTAlgorithm


class ModifyLandCoverByNLCDCCAP(QNSPECTAlgorithm):
    inputVector = "InputVector"
    inputRaster = "InputRaster"
    output = "OutputRaster"
    landUse = "LandUse"

    def initAlgorithm(self, config=None):
        self.coefficients: Dict[str, int] = {}
        root = Path(__file__).parents[3]
        coef_dir = root / "resources" / "coefficients"
        for csvfile in coef_dir.iterdir():
            if csvfile.suffix.lower() == ".csv":
                coef_type = csvfile.stem
                with csvfile.open(newline="") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        name = f"""{coef_type} - {row["lu_name"]}"""
                        self.coefficients[name] = int(row["lu_value"])
        self.choices = sorted(self.coefficients)

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.inputVector,
                "Areas to Modify",
                types=[QgsProcessing.TypeVectorPolygon],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.landUse,
                "Change to Land Cover Class",
                options=self.choices,
                allowMultiple=False,
                defaultValue=[],
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.inputRaster, "Initial Land Cover Raster", defaultValue=None
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

        parameters[self.output].destinationName = "Modified Land Cover"
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

        enum_value = self.parameterAsInt(parameters, self.landUse, context)
        land_use_name = self.choices[enum_value]

        # Rasterize (overwrite with fixed value)
        alg_params = {
            "ADD": False,
            "BURN": self.coefficients[land_use_name],
            "EXTRA": "",
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
        return "modify_land_cover_NLCD_C-CAP"

    def displayName(self):
        return self.tr("Modify Land Cover (NLCD/C-CAP)")

    def group(self):
        return self.tr("Data Preparation")

    def groupId(self):
        return "data_preparation"

    def createInstance(self):
        return ModifyLandCoverByNLCDCCAP()

    def shortHelpString(self):
        return """<html><body>
<a href="https://www.noaa.gov/">Documentation</a>

<h2>Algorithm Description</h2>

<p>The `Modify Land Cover (NLCD/C-CAP)` algorithm changes a section of a raster based on the NLCD/C-CAP land cover name.
This tool is designed to make it easy to change a raster's values in an area based on the name of the new land cover.
The pixels of the input raster layer that overlap with the areas of the input vector layer will be changed to the land cover code of the name selected.</p>

<h2>Input Parameters</h2>

<h3>Areas to Modify</h3>
<p>Polygon vector layer that overlaps the pixels that should be changed.</p>

<h3>Change to Land Cover Class</h3>
<p>The land cover class to be used in the modified areas.</p>

<h3>Initial Land Cover Raster</h3>
<p>Land cover raster that needs to be modified.</p>

<h2>Outputs</h2>

<h3>Modified Land Cover Raster</h3>
<p>The location the modified land cover raster will be saved to.</p>

</body></html>"""
