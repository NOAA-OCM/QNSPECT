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

__author__ = "Abdul Raheem Siddiqui"
__date__ = "2021-12-29"
__copyright__ = "(C) 2021 by NOAA"

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"


from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterDistance,
    QgsProcessingParameterField,
    QgsProcessingParameterRasterDestination,
)
import processing

from QNSPECT.processing.qnspect_algorithm import QNSPECTAlgorithm


class RasterizeSoil(QNSPECTAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                "HydrologicSoilGroupLayer",
                "Soil Layer",
                types=[QgsProcessing.TypeVectorPolygon],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                "HydrologicSoilGroupField",
                "Hydrologic Soil Group Field",
                optional=True,
                type=QgsProcessingParameterField.String,
                parentLayerParameterName="HydrologicSoilGroupLayer",
                allowMultiple=False,
                defaultValue="hydgrpdcd",
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                "KFactorField",
                "K-Factor Field",
                optional=True,
                type=QgsProcessingParameterField.Any,
                parentLayerParameterName="HydrologicSoilGroupLayer",
                allowMultiple=False,
                defaultValue="kffact",
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "RasterCellSize",
                "Raster Cell Size",
                parentParameterName="HydrologicSoilGroupLayer",
                minValue=1e-12,
                defaultValue=30,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                "Hsg",
                "Hydrologic Soil Group Raster",
                createByDefault=True,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                "K_factor", "K-Factor Raster", createByDefault=True, defaultValue=None
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(4, model_feedback)
        results = {}
        outputs = {}

        # Assertions
        if parameters["HydrologicSoilGroupField"]:
            soil_layer = self.parameterAsVectorLayer(
                parameters, "HydrologicSoilGroupLayer", context
            )
            hsg_field = parameters["HydrologicSoilGroupField"]

            for feat in soil_layer.getFeatures():
                if feat[hsg_field] not in [
                    None,
                    "A",
                    "B",
                    "C",
                    "D",
                    "A/D",
                    "B/D",
                    "C/D",
                    "W",
                ]:
                    error_message = f"""Field {hsg_field} contain value(s) other than allowed Hydrologic Soil Groups [Null, 'A', 'B', 'C' , 'D', 'A/D', 'B/D', 'C/D', 'W']"""
                    feedback.reportError(
                        error_message,
                        True,
                    )
                    return {}

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        if parameters["KFactorField"]:

            parameters["K_factor"].destinationName = "K-Factor"

            # Rasterize K-Factor
            alg_params = {
                "BURN": 0,
                "DATA_TYPE": 5,
                "EXTENT": parameters["HydrologicSoilGroupLayer"],
                "EXTRA": "",
                "FIELD": parameters["KFactorField"],
                "HEIGHT": parameters["RasterCellSize"],
                "INIT": None,
                "INPUT": parameters["HydrologicSoilGroupLayer"],
                "INVERT": False,
                "NODATA": -999999,
                "OPTIONS": "",
                "UNITS": 1,
                "WIDTH": parameters["RasterCellSize"],
                "OUTPUT": parameters["K_factor"],
            }
            outputs["RasterizeKfactor"] = processing.run(
                "gdal:rasterize",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            results["K_factor"] = outputs["RasterizeKfactor"]["OUTPUT"]

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        if parameters["HydrologicSoilGroupField"]:
            # Field calculator
            alg_params = {
                "FIELD_LENGTH": 2,
                "FIELD_NAME": "__h_s_g__",
                "FIELD_PRECISION": 0,
                "FIELD_TYPE": 1,
                "FORMULA": f"map_get(map( 'A', 1, 'B', 2, 'C', 3, 'D', 4, 'A/D', 5, 'B/D', 6, 'C/D', 7, 'W', 8, 'Null', 9), coalesce(\"{hsg_field}\", 'Null'))",
                "INPUT": parameters["HydrologicSoilGroupLayer"],
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }
            outputs["FieldCalculator"] = processing.run(
                "native:fieldcalculator",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )

            feedback.setCurrentStep(3)
            if feedback.isCanceled():
                return {}

            parameters["Hsg"].destinationName = "HSG"

            # Rasterize HSG
            alg_params = {
                "BURN": 0,
                "DATA_TYPE": 0,
                "EXTENT": parameters["HydrologicSoilGroupLayer"],
                "EXTRA": "",
                "FIELD": "__h_s_g__",
                "HEIGHT": parameters["RasterCellSize"],
                "INIT": None,
                "INPUT": outputs["FieldCalculator"]["OUTPUT"],
                "INVERT": False,
                "NODATA": 255,
                "OPTIONS": "",
                "UNITS": 1,
                "WIDTH": parameters["RasterCellSize"],
                "OUTPUT": parameters["Hsg"],
            }
            outputs["RasterizeHsg"] = processing.run(
                "gdal:rasterize",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            results["Hsg"] = outputs["RasterizeHsg"]["OUTPUT"]

        return results

    def name(self):
        return "rasterize_soil"

    def displayName(self):
        return self.tr("Rasterize Soil")

    def group(self):
        return self.tr("Data Preparation")

    def groupId(self):
        return "data_preparation"

    def shortHelpString(self):
        return """<html><body><h2>Algorithm description</h2>
<p>The algorithm converts a vector polygon layer into Hydrologic Soul Group and/or K-Factor rasters. The value of the raster pixels is determined by the vector layer's attributes.</p>
<p>Two soil parameters are needed: the hydrologic soils group, which is a measure of how permeable the soils are; and the K-factor, which is a measure of how erodible the soils are.</p>
<h2>Input parameters</h2>
<h3>Soil Layer</h3>
<p>Vector layer representing the soil properties.</p>
<h3>Hydrologic Soil Group Field</h3>
<p>Field of the Soil Layer representing the hydrologic soil group (HSG). The picklist values comes from the fields in the Soil Layer. If this is left emtpy, no HSG raster will be created.</p>
<p>The only valid values for this field are 'A', 'B', 'C' , 'D', 'A/D', 'B/D', 'C/D', 'W', and Null. If the field contains any values other than these, the tool will terminate without output.</p>
<h3>K-Factor Field</h3>
<p>Field of the Soil Layer representing the K-Factor. The picklist values comes from the fields in the Soil Layer. This will default to 'kffact' if it is present in the Soil Layer. If this is left emtpy, no K-Factor raster will be created.</p>
<h3>Raster Cell Size</h3>
<p>The cell size of the output raster(s). The units will default to the units of the CRS of the Soil Layer.</p>
<h2>Outputs</h2>
<h3>Hydrologic Soil Group Raster</h3>
<p>The output path of the Hydrologic Soil Group raster. The raster will inherit the CRS of the Soil Layer if no other units are specified.</p>
<h3>K-Factor Raster</h3>
<p>The output path of the K-Factor raster. The raster will inherit the CRS of the Soil Layer.</p>
<br></body></html>"""

    def createInstance(self):
        return RasterizeSoil()
