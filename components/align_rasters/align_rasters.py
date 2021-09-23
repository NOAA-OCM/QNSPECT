from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterEnum,
    QgsProcessingParameterDistance,
    QgsProcessingParameterRasterDestination,
    QgsExpression,
    QgsRasterLayer,
    QgsMapLayer,
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
                defaultValue=None,  # change the variable names (typical)
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
                defaultValue=10,
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
        feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

        # feedback.pushWarning(self.parameterDefinition('RastersToAlign').valueAsPythonString(parameters["RastersToAlign"], context))

        output_dir = self.parameterAsString(parameters, "OutputDirectory", context)
        extent = parameters.get("ClippingExtent", "")

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

        os.makedirs(output_dir, exist_ok=True)

        ref_layer = self.parameterAsRasterLayer(parameters, "ReferenceRaster", context)

        if extent:  # if extent is provided then clip and buffer
            ref_name = "Aligned" + "_" + ref_layer.name()
            out_path = os.path.join(output_dir, f"{ref_name}.tif")

            feedback.pushWarning(extent)
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

        return results

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        rasters = parameters["rasterstoalign"]
        for i in range(len(rasters)):
            raster = rasters[i]
            if isinstance(raster, str):
                name = os.path.basename(raster)
                path = raster
                lyr = QgsRasterLayer(raster)
                sizex = lyr.rasterUnitsPerPixelX()
                sizey = lyr.rasterUnitsPerPixelY()
            elif isinstance(raster, (QgsRasterLayer, QgsMapLayer)):
                path = raster.source()
                name = os.path.basename()
                sizex = raster.rasterUnitsPerPixelX()
                sizey = raster.rasterUnitsPerPixelY()

            input = QgsProcessingParameterRasterLayer(
                "TemplateRaster",
                "Reference Raster",
                defaultValue=path,
            )

            if sizex < sizey:
                resolution = sizex
            else:
                resolution = sizey

            out_raster = os.path.join(parameters["OutputFolder"].String, name)
            while os.path.exists(out_raster):
                base, ext = os.path.splitext(out_raster)
                out_raster = os.path.join(base + "_1", ext)
            destination = QgsProcessingParameterRasterDestination(
                "Aligned",
                "Aligned",
                createByDefault=True,
                defaultValue=os.path.join(parameters["OutputFolder"].String, name),
            )

            # Warp (reproject)
            alg_params = {
                "DATA_TYPE": 0,
                "EXTRA": "",
                "INPUT": input,
                "MULTITHREADING": False,
                "NODATA": None,
                "OPTIONS": "",
                "RESAMPLING": parameters["samplemethod"],
                "SOURCE_CRS": None,
                "TARGET_CRS": parameters["TemplateRaster"],
                "TARGET_EXTENT": outputs["ClipRasterByExtent"]["OUTPUT"],
                "TARGET_EXTENT_CRS": None,
                "TARGET_RESOLUTION": QgsExpression(
                    str(resolution)
                ).evaluate(),  # hard-coded
                "OUTPUT": destination,
            }
            outputs[out_raster] = processing.run(
                "gdal:warpreproject",
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            results[out_raster] = outputs[out_raster]["OUTPUT"]
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
