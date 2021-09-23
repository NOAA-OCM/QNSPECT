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
)
import processing
import os


class AlignRasters(QgsProcessingAlgorithm):
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

        feedback = QgsProcessingMultiStepFeedback(
            3 + len(parameters["RastersToAlign"]), model_feedback
        )
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
            # Create layer from  to buffer later
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

            # Buffer
            alg_params = {
                "DISSOLVE": False,
                "DISTANCE": parameters["ClipBuffer"],
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

        if extent:  # if extent is provided then clip and buffer
            ref_name = "Aligned" + "_" + ref_layer.name()
            out_path = os.path.join(output_dir, f"{ref_name}.tif")

            # Clip raster by extent
            alg_params = {
                "DATA_TYPE": 0,
                "EXTRA": "",
                "INPUT": parameters["ReferenceRaster"],
                "NODATA": None,
                "OPTIONS": "",
                "PROJWIN": extent,
                "OUTPUT": out_path,
            }

            outputs["ClipRasterByExtent"] = processing.run(
                "gdal:cliprasterbyextent",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )

            context.addLayerToLoadOnCompletion(
                outputs["ClipRasterByExtent"]["OUTPUT"],
                QgsProcessingContext.LayerDetails(
                    ref_name, context.project(), ref_name
                ),
            )

        else:  # set extent to reference raster extent
            extent = parameters["ReferenceRaster"]

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        if len(parameters["RastersToAlign"]) == 0:
            return results

        size_x = ref_layer.rasterUnitsPerPixelX()
        size_y = ref_layer.rasterUnitsPerPixelY()

        # select lowest resolution
        if size_x < size_y:
            resolution = size_x
        else:
            resolution = size_y

        rasters_to_align = self.parameterAsLayerList(
            parameters, "RastersToAlign", context
        )

        for i, rast in enumerate(rasters_to_align, start=4):

            # to do: get name directly
            rast_name = "Aligned" + "_" + rast.name()
            out_path = os.path.join(output_dir, f"{rast_name}.tif")

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
                    rast_name, context.project(), rast_name
                ),
            )

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
        return """<html><body><h2>Algorithm description</h2>
<p></p>
<h2>Input parameters</h2>
<h3>Reference Raster</h3>
<p></p>
<h3>Rasters to Align</h3>
<p></p>
<h3>Resampling Method</h3>
<p></p>
<h3>Watershed to Mask</h3>
<p></p>
<h3>Mask Buffer</h3>
<p></p>
<h3>Temp Raster Align</h3>
<p></p>
<h3>Aligned Soil</h3>
<p></p>
<h3>Aligned</h3>
<p></p>
<h2>Outputs</h2>
<h3>Aligned Soil</h3>
<p></p>
<h3>Aligned</h3>
<p></p>
<br></body></html>"""

    def createInstance(self):
        return AlignRasters()
