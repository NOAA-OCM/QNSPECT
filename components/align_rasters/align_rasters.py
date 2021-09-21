from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterMultipleLayers
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsExpression
from qgis.core import QgsRasterLayer, QgsMapLayer
import processing
import os


class AlignRasters(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "TemplateRaster",
                "Reference Raster",
                defaultValue=None,  # change the variable names (typical)
            )
        )
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                "rasterstoalign",
                "Rasters to Align",
                layerType=QgsProcessing.TypeRaster,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "samplemethod",
                "Sample Method",
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
            QgsProcessingParameterVectorLayer(
                "watershed",
                "Watershed to Mask",
                optional=True,
                types=[QgsProcessing.TypeVectorPolygon],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "WatershedBuffer",
                "Mask Buffer",
                optional=True,
                parentParameterName="watershed",
                minValue=0,
                defaultValue=10,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "TempRasterAlign", "Temp Raster Align", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                "AlignedSoil", "Aligned Soil", createByDefault=True, defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                "Aligned", "Aligned", createByDefault=True, defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                'OutputFolder',
                'Results Folder', 
                behavior=QgsProcessingParameterFile.Folder,
                fileFilter='All files (*.*)',
                defaultValue=None
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

        # Clip raster by extent
        alg_params = {
            "DATA_TYPE": 0,
            "EXTRA": "",
            "INPUT": parameters["TemplateRaster"],
            "NODATA": None,
            "OPTIONS": "",
            "PROJWIN": parameters['watershed'],
            "OUTPUT": parameters["AlignedSoil"],
        }
        outputs["ClipRasterByExtent"] = processing.run(
            "gdal:cliprasterbyextent",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        results["AlignedSoil"] = outputs["ClipRasterByExtent"]["OUTPUT"]

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        rasters = parameters['rasterstoalign']
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
            
            out_raster = os.path.join(
                parameters['OutputFolder'].String,
                name
            )
            while os.path.exists(out_raster):
                base, ext = os.path.splitext(out_raster)
                out_raster = os.path.join(base + '_1', ext)
            destination = QgsProcessingParameterRasterDestination(
                "Aligned", 
                "Aligned", 
                createByDefault=True, 
                defaultValue=os.path.join(
                    parameters['OutputFolder'].String,
                    name
                )
            )

            # Warp (reproject)
            alg_params = {
                "DATA_TYPE": 0,
                "EXTRA": "",
                "INPUT": input,
                "MULTITHREADING": False,
                "NODATA": None,
                "OPTIONS": "",
                "RESAMPLING": parameters['samplemethod'],
                "SOURCE_CRS": None,
                "TARGET_CRS": parameters["TemplateRaster"],
                "TARGET_EXTENT": outputs["ClipRasterByExtent"]["OUTPUT"],
                "TARGET_EXTENT_CRS": None,
                "TARGET_RESOLUTION": QgsExpression(str(resolution)).evaluate(),  # hard-coded
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
        return ""

    def groupId(self):
        return ""

    def shortHelpString(self):
        return """<html><body><h2>Algorithm description</h2>
<p></p>
<h2>Input parameters</h2>
<h3>Reference Raster</h3>
<p></p>
<h3>Rasters to Align</h3>
<p></p>
<h3>Sample Method</h3>
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
