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


import processing
import os
from typing import Union

from qgis.core import (
    QgsProcessing,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterEnum,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterBoolean,
    QgsProcessingContext,
    QgsUnitTypes,
    QgsProcessingParameterNumber,
    QgsRasterLayer,
    QgsVectorLayer,
)

from QNSPECT.processing.qnspect_algorithm import QNSPECTAlgorithm
from QNSPECT.processing.algorithms.qnspect_utils import select_group, create_group


class AlignRasters(QNSPECTAlgorithm):
    rasterCellSize: str = "RasterCellSize"
    resamplingMethods = [
        ("Nearest Neighbour", "near"),
        ("Bilinear", "bilinear"),
        ("Cubic", "cubic"),
        ("Cubic Spline", "cubicspline"),
        ("Lanczos Windowed Sinc", "lanczos"),
        ("Average", "average"),
        ("Mode", "mode"),
        ("Maximum", "max"),
        ("Minimum", "min"),
        ("Median", "med"),
        ("First Quartile", "q1"),
        ("Third Quartile", "q3"),
    ]

    def __init__(self):
        super().__init__()
        self.load_outputs = False

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
                options=[m[0] for m in self.resamplingMethods],
                allowMultiple=False,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "MaskLayer",
                "Mask Layer",
                optional=True,
                types=[QgsProcessing.TypeVectorPolygon],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "MaskBuffer",
                "Mask Buffer",
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
            QgsProcessingParameterBoolean(
                "LoadOutputs",
                "Open output files after running algorithm",
                defaultValue=True,
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
                3 + len(parameters["RastersToAlign"]), model_feedback
            )
        else:
            feedback = QgsProcessingMultiStepFeedback(3, model_feedback)
        results = {}
        outputs = {}

        output_dir = self.parameterAsString(parameters, "OutputDirectory", context)
        self.load_outputs = self.parameterAsBool(parameters, "LoadOutputs", context)
        ref_layer = self.parameterAsRasterLayer(parameters, "ReferenceRaster", context)
        resample_method = self.parameterAsEnum(parameters, "ResamplingMethod", context)

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

        if parameters["MaskLayer"]:
            if all(
                [
                    parameters["MaskBuffer"],
                    parameters["MaskBuffer"] != 0,
                ]
            ):

                # Reprojecting Mask Layer to Reference Raster CRS because
                # Mask Layer and Buffer distance can be in different CRS
                # If the distance is in projected units (meters etc) and Mask Layer in Geographic (degrees)
                # the buffer algorithm will treat distance in degrees ignoring actual buffer distance units
                alg_params = {
                    "INPUT": parameters["MaskLayer"],
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
                    "DISTANCE": parameters["MaskBuffer"],
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
                mask_layer = outputs["Buffer"]["OUTPUT"]
            else:
                mask_layer = self.parameterAsVectorLayer(
                    parameters, "MaskLayer", context
                )

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}
        os.makedirs(output_dir, exist_ok=True)
        res_x, res_y, user_size = self.find_pixel_size(ref_layer, parameters, context)

        # Reference raster will always be aligned for this reason:
        # GDAL will write other new rasters with standard projection string
        # if reference is not aligned, it will have old projection which will be same
        # in theory but some software like ArcGIS can interpret both projections as different
        ref_source = ref_layer.source()
        rasters_to_align = [ref_layer]
        rasters_to_align += self.parameterAsLayerList(
            parameters, "RastersToAlign", context
        )

        all_out_paths = []

        enum_start = 3
        for i, rast in enumerate(rasters_to_align, start=enum_start):
            # Prevent the reference raster from being alignd multiple times
            if (i != enum_start) and (rast.source() == ref_source):
                continue

            rast_name = rast.name()
            out_path = os.path.join(output_dir, f"{rast_name}.tif")

            j = 1  # prevent self overwriting in algorithm outputs if two rasters have same display name
            while out_path in all_out_paths:
                rast_name = f"{rast.name()}_{j}"
                out_path = os.path.join(output_dir, f"{rast_name}.tif")
                j += 1
            all_out_paths.append(out_path)

            if i == enum_start:  # first item will be ref_layer
                if parameters["MaskLayer"]:
                    if not user_size:
                        # mask ref layer with crop_to_cutline=True to match original cell alignment to preserve integrity
                        outputs[rast_name] = self.mask_raster(
                            rast,
                            mask_layer,
                            out_path,
                            True,
                            context=context,
                            feedback=feedback,
                        )
                    else:
                        temp_rast_layer = self.warp_raster(
                            rast,
                            ref_layer,
                            mask_layer,
                            resample_method,
                            res_x,
                            res_y,
                            context=context,
                            feedback=feedback,
                        )["OUTPUT"]
                        outputs[rast_name] = self.mask_raster(
                            temp_rast_layer,
                            mask_layer,
                            out_path,
                            False,
                            context=context,
                            feedback=feedback,
                        )
                    ref_layer = QgsRasterLayer(
                        outputs[rast_name]["OUTPUT"], "ref layer"
                    )
                else:
                    outputs[rast_name] = self.warp_raster(
                        rast,
                        ref_layer,
                        ref_layer,
                        resample_method,
                        res_x,
                        res_y,
                        out_path,
                        context=context,
                        feedback=feedback,
                    )

            elif parameters["MaskLayer"]:
                temp_rast_layer = self.warp_raster(
                    rast,
                    ref_layer,
                    ref_layer,
                    resample_method,
                    res_x,
                    res_y,
                    context=context,
                    feedback=feedback,
                )["OUTPUT"]
                outputs[rast_name] = self.mask_raster(
                    temp_rast_layer,
                    mask_layer,
                    out_path,
                    False,
                    context=context,
                    feedback=feedback,
                )

            else:
                outputs[rast_name] = self.warp_raster(
                    rast,
                    ref_layer,
                    ref_layer,
                    resample_method,
                    res_x,
                    res_y,
                    out_path,
                    context=context,
                    feedback=feedback,
                )

            if self.load_outputs:
                context.addLayerToLoadOnCompletion(
                    outputs[rast_name]["OUTPUT"],
                    QgsProcessingContext.LayerDetails(
                        rast_name, context.project(), rast_name
                    ),
                )
            results[rast_name] = outputs[rast_name]["OUTPUT"]

            feedback.setCurrentStep(i)
            if feedback.isCanceled():
                return {}

        return results

    def postProcessAlgorithm(self, context, feedback):
        if self.load_outputs:
            project = context.project()
            root = project.instance().layerTreeRoot()  # get base level node

            create_group("Aligned", root)
            select_group("Aligned")  # so that layers are spit out within group

        return {}

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
<h3>Mask Layer [optional]</h3>
<p>If set, all values outside of this layer will get no data value. If this is not set, the aligned rasters will be clipped to the extent of the Reference Raster.</p>
<h3>Mask Buffer [optional]</h3>
<p>Buffer added around the Mask Layer. If the Mask Layer is not provided, no buffer will be applied.</p>
<h3>Output Cell Size [optional]</h3>
<p>The raster cell size of the output rasters. If this is not set, the cell size will be the same as the reference raster.</p>
<h2>Outputs</h2>
<h3>Output Directory</h3>
<p>The output directory the aligned rasters will be saved to. The aligned rasters will have the same name as their source files.</p>
<br></body></html>"""

    def createInstance(self):
        return AlignRasters()

    def find_pixel_size(self, rast_layer, parameters, context) -> tuple:
        user_size = self.parameterAsInt(parameters, self.rasterCellSize, context)
        if user_size:
            return user_size, user_size, True
        else:
            ras_size_x = rast_layer.rasterUnitsPerPixelX()
            ras_size_y = rast_layer.rasterUnitsPerPixelY()
            return ras_size_x, ras_size_y, False

    def mask_raster(
        self,
        rast: QgsRasterLayer,
        mask_layer: Union[str, QgsVectorLayer],
        out_path: str = QgsProcessing.TEMPORARY_OUTPUT,
        crop_to_cutline: bool = False,
        extra: str = "-wo CUTLINE_ALL_TOUCHED=TRUE",
        context=None,
        feedback=None,
    ):
        # Clip raster by mask layer
        alg_params = {
            "ALPHA_BAND": False,
            "CROP_TO_CUTLINE": crop_to_cutline,
            "DATA_TYPE": 0,  # Use Input Layer Data Type
            "EXTRA": extra,
            "INPUT": rast,
            "KEEP_RESOLUTION": False,
            "MASK": mask_layer,
            "MULTITHREADING": False,
            "NODATA": None,
            "OPTIONS": "",
            "SET_RESOLUTION": False,
            "SOURCE_CRS": None,
            "TARGET_CRS": None,
            "X_RESOLUTION": None,
            "Y_RESOLUTION": None,
            "OUTPUT": out_path,
        }
        return processing.run(
            "gdal:cliprasterbymasklayer",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )

    def warp_raster(
        self,
        rast: QgsRasterLayer,
        ref_layer,
        extent_layer,
        resample: int,
        res_x: float,
        res_y: float,
        out_path: str = QgsProcessing.TEMPORARY_OUTPUT,
        extra: str = "",
        context=None,
        feedback=None,
    ):
        # Warp (reproject)
        alg_params = {
            "DATA_TYPE": 0,
            "INPUT": rast,
            "MULTITHREADING": False,
            "NODATA": None,
            "OPTIONS": "",
            "RESAMPLING": resample,
            "SOURCE_CRS": None,
            "TARGET_CRS": ref_layer,
            "TARGET_EXTENT": extent_layer,
            "TARGET_EXTENT_CRS": None,
            "TARGET_RESOLUTION": None,
            "OUTPUT": out_path,
            "EXTRA": f"-tr {res_x} {res_y} {extra}",
        }
        return processing.run(
            "gdal:warpreproject",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
