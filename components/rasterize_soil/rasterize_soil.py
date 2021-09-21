from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterNumber
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
            QgsProcessingParameterNumber(
                "RasterCellSizeCRSUnits",
                "Raster Cell Size (CRS Units)",
                type=QgsProcessingParameterNumber.Double,
                minValue=1e-12,
                maxValue=1.79769e308,
                defaultValue=30,
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                "HydrologicSoilGroupField",
                "Hydrologic Soil Group Field",
                type=QgsProcessingParameterField.String,
                parentLayerParameterName="HydrologicSoilGroupLayer",
                allowMultiple=False,
                defaultValue="hydgrpdcd",
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                "SoilRasterized",
                "Soil Rasterized",
                createByDefault=True,
                defaultValue=None,
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(4, model_feedback)
        results = {}
        outputs = {}

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Assertions

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

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Raise exception
        alg_params = {"CONDITION": "1 = 2", "MESSAGE": "sadfasdf"}
        outputs["RaiseException"] = processing.run(
            "native:raiseexception",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Rasterize (vector to raster)
        alg_params = {
            "BURN": 0,
            "DATA_TYPE": 0,  # Byte
            "EXTENT": outputs["FieldCalculator"]["OUTPUT"],
            "EXTRA": "",
            "FIELD": "__h_s_g__",
            "HEIGHT": parameters["RasterCellSizeCRSUnits"],
            "INIT": None,
            "INPUT": outputs["FieldCalculator"]["OUTPUT"],
            "INVERT": False,
            "NODATA": 255,
            "OPTIONS": "",
            "UNITS": 1,
            "WIDTH": parameters["RasterCellSizeCRSUnits"],
            "OUTPUT": parameters["SoilRasterized"],
        }
        outputs["RasterizeVectorToRaster"] = processing.run(
            "gdal:rasterize",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        results["SoilRasterized"] = outputs["RasterizeVectorToRaster"]["OUTPUT"]
        return results

    def name(self):
        return "Rasterize Soil"

    def displayName(self):
        return "Rasterize Soil"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return RasterizeSoil()
