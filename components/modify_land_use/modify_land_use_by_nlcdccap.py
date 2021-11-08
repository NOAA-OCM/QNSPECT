from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterRasterDestination,
)
from typing import Dict
import csv
import processing
from pathlib import Path


class ModifyLandUseByNLCDCCAP(QgsProcessingAlgorithm):
    inputVector = "InputVector"
    inputRaster = "InputRaster"
    output = "OutputRaster"
    landUse = "LandUse"

    def initAlgorithm(self, config=None):
        self.coefficients: Dict[str, int] = {}
        root = Path(__file__).parent.parent.parent
        coef_dir = root / "resources" / "coefficients"
        for csvfile in coef_dir.iterdir():
            if csvfile.suffix.lower() == ".csv":
                coef_type = csvfile.name
                with csvfile.open(newline="") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        name = f"""{coef_type} - {row["lu_name"]}"""
                        self.coefficients[name] = int(row["lu_value"])
        self.choices = sorted(self.coefficients)

        self.addParameter(
            QgsProcessingParameterEnum(
                self.landUse,
                "Land Use",
                options=self.choices,
                allowMultiple=False,
                defaultValue=[],
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.inputVector,
                "Area to Change",
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
                self.output, "Modified Raster", createByDefault=True, defaultValue=None
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

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

        enum_value = self.parameterAsInt(parameters, self.landUse, context)
        land_use_name = self.choices[enum_value]
        # Rasterize (overwrite with fixed value)
        alg_params = {
            "ADD": False,
            "BURN": self.coefficients[land_use_name],
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
        return f"Modify Land Use by NLCD/CCAP"

    def displayName(self):
        return f"Modify Land Use by NLCD/CCAP"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return ModifyLandUseByNLCDCCAP()
