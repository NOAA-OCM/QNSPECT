from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterRasterDestination
import processing


class RasterizeSoil(QgsProcessingAlgorithm):
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
                "Hsg", "HSG Raster", createByDefault=True, defaultValue=None
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
        feedback = QgsProcessingMultiStepFeedback(6, model_feedback)
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

            parameters["K_factor"].destinationName = "K_Factor"

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
                "NODATA": -9999,
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
        return "Rasterize Soil"

    def displayName(self):
        return "Rasterize Soil"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def shortHelpString(self):
        return """<html><body><h2>Algorithm description</h2>
<p></p>
<h2>Input parameters</h2>
<h3>Soil Layer</h3>
<p></p>
<h3>Hydrologic Soil Group Field</h3>
<p></p>
<h3>K-Factor Field</h3>
<p></p>
<h3>Raster Cell Size</h3>
<p></p>
<h2>Outputs</h2>
<h3>HSG Raster</h3>
<p></p>
<h3>K-Factor Raster</h3>
<p></p>
<br></body></html>"""

    def createInstance(self):
        return RasterizeSoil()
