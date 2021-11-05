from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterEnum,
    QgsProcessingParameterDistance,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFolderDestination,
    QgsProcessingContext,
    QgsUnitTypes,
)
import processing
import os


class AlignRasters(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "ReferenceRaster", "Reference Raster", defaultValue=None,
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

            feedback.setCurrentStep(1)
            if feedback.isCanceled():
                return {}

            # Check if the degrees is set beyond a reasonable buffer and lower it if it is
            buffer_distance = parameters["ClipBuffer"]
            raster = self.parameterAsRasterLayer(parameters, "ReferenceRaster", context)
            crs = raster.crs()
            units = QgsUnitTypes.toString(crs.mapUnits())
            if units.lower() == "degrees":
                if buffer_distance > 1:
                    feedback.pushWarning(
                        "Clip buffer was set to above 1. The buffer was changed to 1 degree."
                    )
                    buffer_distance = 1.0

            # Buffer
            alg_params = {
                "DISSOLVE": False,
                "DISTANCE": buffer_distance,
                "END_CAP_STYLE": 0,
                "INPUT": outputs["CreateLayerFromExtent"]["OUTPUT"],
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
        ref_layer = self.parameterAsRasterLayer(parameters, "ReferenceRaster", context)
        size_x = ref_layer.rasterUnitsPerPixelX()
        size_y = ref_layer.rasterUnitsPerPixelY()

        # select lowest resolution
        if size_x < size_y:
            resolution = size_x
        else:
            resolution = size_y

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
        return "Align Rasters"

    def displayName(self):
        return "Align Rasters"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def shortHelpString(self):
        return """<html><body>
<h2>Algorithm description</h2>
<p>The algorithm aligns one or more rasters to a reference raster. The aligned rasters will adopt the CRS, cell size, and origin of the reference raster. The aligned rasters will be saved as TIFF files.</p>
<h2>Input parameters</h2>
<h3>Reference Raster</h3>
<p>The raster used for determining the CRS, cell size, and origin coordinates of the output rasters. If the reference raster has non-square pixels, the aligned raster pixel sizes will be the smallest length.</p>
<h3>Rasters to Align</h3>
<p>The rasters that will be aligned to the reference raster.</p>
<h3>Resampling Method</h3>
<p>The resampling method used for determining the value of aligned rasters' pixel value. The algorithms are identical to the algorithms executed in GDAL Warp.</p>
<h3>Clipping Extent [optional]</h3>
<p>The extent the aligned rasters will be clipped to. Smaller raster extents will decrease file size and processing time for later components. Thus, it is suggested the rasters be clipped to the area of interest of the project. Common intputs would include a watershed or county boundary.</p>
<p>If this is not set, the aligned rasters will be clipped to the extent of the Reference Raster.</p>
<h3>Clip Buffer [optional]</h3>
<p>Buffer added around the Clipping Extent. A small buffer around the project area of interest may increase the accuracy of drainage algorithms.</p>
<p>If the Clipping Extent is not set, no buffer will be applied.</p>
<h2>Outputs</h2>
<h3>Output Directory</h3>
<p>The output directory the aligned rasters will be saved to. The aligned rasters will share the name of their source files. If more than one raster share the same source name, numbers will be added to the end in the order they are processed.</p>
<br></body></html>"""

    def createInstance(self):
        return AlignRasters()
