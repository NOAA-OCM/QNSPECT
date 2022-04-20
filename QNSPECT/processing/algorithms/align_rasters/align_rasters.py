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
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterEnum,
    QgsProcessingParameterDistance,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFolderDestination,
    QgsProcessingContext,
    QgsUnitTypes,
    QgsProcessingParameterNumber,
)
import processing
import os

from QNSPECT.processing.qnspect_algorithm import QNSPECTAlgorithm


class AlignRasters(QNSPECTAlgorithm):
    rasterCellSize: str = "RasterCellSize"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "ReferenceRaster",
                "Reference Raster",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                "RastersToAlign",
                "Rasters to Align",
                layerType=QgsProcessing.TypeRaster,
                optional=True,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "ResamplingMethod",
                "Resampling Method",
                options=[
                    "Nearest Neighbor",
                    "Bilinear",
                    "Cubic",
                    "Cubic Spline",
                    "Lanczos Windowed Sinc",
                    "Average",
                    "Mode",
                    "Maximum",
                    "Minimum",
                    "Median",
                    "First Quartile",
                    "Third Quartile",
                ],
                allowMultiple=False,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterExtent(
                "ClippingExtent", "Clipping Extent", optional=True, defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "ClipBuffer",
                "Clip Buffer",
                optional=True,
                parentParameterName="ReferenceRaster",
                minValue=0,
                defaultValue=100,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.rasterCellSize,
                "Output Cell Size",
                optional=True,
                type=QgsProcessingParameterNumber.Double,
                minValue=0.000001,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                "OutputDirectory",
                "Output Directory",
                createByDefault=True,
                defaultValue=None,
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model

        if parameters["RastersToAlign"]:
            feedback = QgsProcessingMultiStepFeedback(
                4 + len(parameters["RastersToAlign"]), model_feedback
            )
        else:
            feedback = QgsProcessingMultiStepFeedback(4, model_feedback)
        results = {}
        outputs = {}

        output_dir = self.parameterAsString(parameters, "OutputDirectory", context)
        extent = parameters.get("ClippingExtent", "")
        ref_layer = self.parameterAsRasterLayer(parameters, "ReferenceRaster", context)

        # Check if the reference raster is in a geographic CRS and terminate if it is
        # This will:
        # (a) prevent known errors in output when using a geographic CRS, and
        # (b) better reflect expected inputs for how the analysis tools are processed.
        ref_layer_crs = ref_layer.crs()
        units = QgsUnitTypes.toString(ref_layer_crs.mapUnits())
        if units.lower() == "degrees":
            feedback.reportError(
                "The reference raster must be in a projected coordinate system."
            )
            return {}

        # Get buffered extents
        # Use QGIS algorithms so as to handle unit conversion and projection per context
        if all(
            [
                parameters["ClippingExtent"],
                parameters["ClipBuffer"],
                parameters["ClipBuffer"] != 0,
            ]
        ):
            # Create layer from extent to buffer later
            alg_params = {
                "INPUT": parameters["ClippingExtent"],
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }
            outputs["CreateLayerFromExtent"] = processing.run(
                "native:extenttolayer",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            # Reprojecting Buffer Extent Layer to Reference Raster CRS because
            # Clipping extent and Buffer distance can be in different CRS
            # If the distance is in projected units (meters etc) and Clipping Extent in Geographic (degrees)
            # the buffer algorithm will treat distance in degrees ignoring actual buffer distance units
            alg_params = {
                "INPUT": outputs["CreateLayerFromExtent"]["OUTPUT"],
                "OPERATION": "",
                "TARGET_CRS": ref_layer_crs,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }
            outputs["ReprojectLayer"] = processing.run(
                "native:reprojectlayer",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )

            feedback.setCurrentStep(1)
            if feedback.isCanceled():
                return {}

            # Buffer
            alg_params = {
                "DISSOLVE": False,
                "DISTANCE": parameters["ClipBuffer"],
                "END_CAP_STYLE": 0,
                "INPUT": outputs["ReprojectLayer"]["OUTPUT"],
                "JOIN_STYLE": 0,
                "MITER_LIMIT": 2,
                "SEGMENTS": 5,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }
            outputs["Buffer"] = processing.run(
                "native:buffer",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            extent = outputs["Buffer"]["OUTPUT"]

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        os.makedirs(output_dir, exist_ok=True)

        resolution = self.find_pixel_size(ref_layer, parameters, context)

        if extent:
            # if extent is provided then clip raster to get new updated clip extents
            # this is step is necessary to make sure reference raster cells do not get shifted
            # though, for non square cells reference raster will also shift

            # Clip raster by extent
            alg_params = {
                "DATA_TYPE": 0,
                "EXTRA": "",
                "INPUT": parameters["ReferenceRaster"],
                "NODATA": None,
                "OPTIONS": "",
                "PROJWIN": extent,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }

            outputs["ClipRasterByExtent"] = processing.run(
                "gdal:cliprasterbyextent",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            extent = outputs["ClipRasterByExtent"]["OUTPUT"]

        else:  # set extent to reference raster extent
            extent = parameters["ReferenceRaster"]

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Reference raster will always be aligned for these reasons:
        # It may have non-square cell size, and
        # QGIS will write other new rasters with standard projection string
        # if reference is not aligned, it will have old projection which will be same
        # in theory but some software like ArcGIS can interpret both projections as different
        ref_source = ref_layer.source()
        rasters_to_align = [ref_layer]
        rasters_to_align += self.parameterAsLayerList(
            parameters, "RastersToAlign", context
        )

        all_out_paths = []

        enum_start = 4
        for i, rast in enumerate(rasters_to_align, start=enum_start):
            # Prevent the reference raster from being alignd multiple times
            if (i != enum_start) and (rast.source() == ref_source):
                continue

            rast_name = rast.name()
            out_path = os.path.join(output_dir, f"{rast_name}.tif")

            # prevent self overwriting in algorithm outputs if two rasters have same display name
            j = 1
            while out_path in all_out_paths:
                rast_name = f"{rast.name()}_{j}"
                out_path = os.path.join(output_dir, f"{rast_name}.tif")
                j += 1
            all_out_paths.append(out_path)

            # Warp (reproject)
            alg_params = {
                "DATA_TYPE": 0,
                "EXTRA": "",
                "INPUT": rast,
                "MULTITHREADING": False,
                "NODATA": None,
                "OPTIONS": "",
                "RESAMPLING": parameters["ResamplingMethod"],
                "SOURCE_CRS": None,
                "TARGET_CRS": parameters["ReferenceRaster"],
                "TARGET_EXTENT": extent,
                "TARGET_EXTENT_CRS": None,
                "TARGET_RESOLUTION": resolution,
                "OUTPUT": out_path,
            }
            outputs[rast_name] = processing.run(
                "gdal:warpreproject",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )

            context.addLayerToLoadOnCompletion(
                outputs[rast_name]["OUTPUT"],
                QgsProcessingContext.LayerDetails(
                    f"Aligned {rast_name}", context.project(), rast_name
                ),  # to do: Remove Aligned from name and group layers
            )

            results[rast_name] = outputs[rast_name]["OUTPUT"]

            feedback.setCurrentStep(i)
            if feedback.isCanceled():
                return {}

        return results

    def name(self):
        return "align_rasters"

    def displayName(self):
        return self.tr("Align Rasters")

    def group(self):
        return self.tr("Data Preparation")

    def groupId(self):
        return "data_preparation"

    def shortHelpString(self):
        return """<html><body>
<h2>Algorithm description</h2>
<p>The algorithm aligns one or more rasters to a reference raster. The aligned rasters will adopt the CRS, cell size, and origin of the reference raster. The aligned rasters will be saved as TIFF files.</p>
<h2>Input parameters</h2>
<h3>Reference Raster</h3>
<p>The raster used for determining the CRS and origin coordinates of the output rasters.</p>
<h3>Rasters to Align</h3>
<p>The rasters that will be aligned to the reference raster.</p>
<h3>Resampling Method</h3>
<p>The resampling method used for determining the value of aligned rasters' pixel value. The algorithms are identical to the algorithms executed in GDAL Warp.</p>
<h3>Clipping Extent [optional]</h3>
<p>The extent the aligned rasters will be clipped to. If this is not set, the aligned rasters will be clipped to the extent of the Reference Raster.</p>
<h3>Clip Buffer [optional]</h3>
<p>Buffer added around the Clipping Extent. If the Clipping Extent is not set, no buffer will be applied.</p>
<h3>Output Cell Size [optional]</h3>
<p>The raster cell size of the output rasters. If this is not set, the cell size will be the same as the reference raster. If the reference raster has non-square pixels, the aligned raster(s) pixel size will be the smallest length.</p>
<h2>Outputs</h2>
<h3>Output Directory</h3>
<p>The output directory the aligned rasters will be saved to. The aligned rasters will share the name of their source files. If more than one raster share the same source name, numbers will be added to the end in the order they are processed.</p>
<br></body></html>"""

    def createInstance(self):
        return AlignRasters()

    def find_pixel_size(self, ref_layer, parameters, context):
        user_size = self.parameterAsInt(parameters, self.rasterCellSize, context)
        if user_size:
            return user_size
        else:
            ref_size_x = ref_layer.rasterUnitsPerPixelX()
            ref_size_y = ref_layer.rasterUnitsPerPixelY()
            if ref_size_x < ref_size_y:
                return ref_size_x
            else:
                return ref_size_y
