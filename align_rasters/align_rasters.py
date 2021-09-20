from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterMultipleLayers
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsExpression
import processing


class AlignRasters(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "TemplateRaster", "Reference Raster", defaultValue=None
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
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                    "new item",
                ],
                allowMultiple=False,
                defaultValue=None,
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
            "PROJWIN": "-10857764.687300000,-10847402.800600000,3885443.311200000,3890820.388900000 [EPSG:3857]",
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

        # Warp (reproject)
        alg_params = {
            "DATA_TYPE": 0,
            "EXTRA": "",
            "INPUT": parameters["TempRasterAlign"],
            "MULTITHREADING": False,
            "NODATA": None,
            "OPTIONS": "",
            "RESAMPLING": 0,
            "SOURCE_CRS": None,
            "TARGET_CRS": parameters["TemplateRaster"],
            "TARGET_EXTENT": outputs["ClipRasterByExtent"]["OUTPUT"],
            "TARGET_EXTENT_CRS": None,
            "TARGET_RESOLUTION": QgsExpression("3").evaluate(),
            "OUTPUT": parameters["Aligned"],
        }
        outputs["WarpReproject"] = processing.run(
            "gdal:warpreproject",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        results["Aligned"] = outputs["WarpReproject"]["OUTPUT"]
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
