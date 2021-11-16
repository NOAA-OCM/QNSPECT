from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsProcessingParameterFeatureSource
import processing


class ModifyLandUseByName(QgsProcessingAlgorithm):
    inputTable = "InputTable"
    inputVector = "InputVector"
    inputRaster = "InputRaster"
    output = "OutputRaster"
    landUse = "LandUse"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.inputTable,
                "Land Use Lookup Table",
                types=[QgsProcessing.TypeVector],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.landUse,
                "Name of Land Use to Apply",
                multiLine=False,
                defaultValue="",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.inputVector,
                "Area to Modify",
                types=[QgsProcessing.TypeVectorPolygon],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.inputRaster, "Land Use Raster", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.output,
                "Modified Land Use",
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

        # Find the named values
        coefficient_name = self.parameterAsString(parameters, self.landUse, context)
        name_compare = coefficient_name.lower().replace(" ", "")
        table = self.parameterAsVectorLayer(parameters, self.inputTable, context)
        if "lu_name" not in table.fields().names():
            feedback.reportError('Field "lu_name" required for the coefficients table.')
            return {}
        if "lu_value" not in table.fields().names():
            feedback.reportError(
                'Field "lu_value" required for the coefficients table.'
            )
            return {}
        for feature in table.getFeatures():
            candidate = feature.attribute("lu_name").lower().replace(" ", "")
            if candidate == name_compare:
                lu_value = int(feature.attribute("lu_value"))
                break
        else:
            feedback.reportError(f"Unable to find {coefficient_name} in the table.")
            return {}

        # Uses clip raster to get a copy of the original raster
        # Some other method of copying in a way that allows for temporary output would be better for this part
        alg_params = {
            "DATA_TYPE": 0,
            "EXTRA": "",
            "INPUT": parameters[self.inputRaster],
            "NODATA": None,
            "OPTIONS": "",
            "PROJWIN": parameters[self.inputRaster],
            "OUTPUT": parameters[self.output],
        }
        outputs["ClipRasterByExtent"] = processing.run(
            "gdal:cliprasterbyextent",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Rasterize (overwrite with fixed value)
        alg_params = {
            "ADD": False,
            "BURN": lu_value,
            "EXTRA": "",
            "INPUT": parameters[self.inputVector],
            "INPUT_RASTER": outputs["ClipRasterByExtent"]["OUTPUT"],
        }
        outputs["RasterizeOverwriteWithFixedValue"] = processing.run(
            "gdal:rasterize_over_fixed_value",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        return results

    def name(self):
        return "Modify Land Use (Custom Name)"

    def displayName(self):
        return "Modify Land Use (Custom Name)"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return ModifyLandUseByName()
