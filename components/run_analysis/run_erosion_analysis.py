from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

from analysis_utils import (
    extract_lookup_table,
    assign_land_use_field_to_raster,
    perform_raster_math,
    convert_raster_data_type_to_float,
    grass_material_transport,
)
from Curve_Number import Curve_Number

DEFAULT_URBAN_K_FACTOR_VALUE = 0.3

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFolderDestination,
    Qgis,
    QgsProcessingParameterDefinition,
    QgsUnitTypes,
)
import processing


class RunErosionAnalysis(QgsProcessingAlgorithm):
    lookupTable = "LookupTable"
    landUseType = "LandUseType"
    soilsRasterRaw = "SoilsRasterNotKfactor"
    soilsRaster = "SoilsRaster"
    elevationRaster = "ElevationRaster"
    rainfallRaster = "RainfallRaster"
    landUseRaster = "LandUseRaster"
    lengthSlopeRaster = "LengthSlopeRaster"
    projectLocation = "ProjectLocation"
    testOutFolder = Path(r"C:\Users\itodd\Downloads\sample")

    def initAlgorithm(self, config=None):
        test_folder = Path(r"C:\NSPECT\HI_Sample_Data")
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.elevationRaster,
                "Elevation Raster",
                defaultValue=r"C:\NSPECT\wsdelin\HI_SampleWS\demfill.tif",
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.rainfallRaster,
                "R-Factor Raster (Rainfall)",
                defaultValue=str(test_folder / "HI_rfactor.tif"),
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.landUseRaster,
                "Land Use Raster",
                defaultValue=str(test_folder / "HI_CCAP05.tif"),
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.soilsRasterRaw,
                "Soils Raster",
                defaultValue=str(test_folder / "soils1.tif"),
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.soilsRaster,
                "K-factor Raster (Soils)",
                defaultValue=str(test_folder / "soilsk1.tif"),
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.landUseType,
                "Land Use Type",
                options=["Custom", "C-CAP", "NLCD"],
                allowMultiple=False,
                defaultValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.lookupTable,
                "Land Use Lookup Table",
                optional=True,
                types=[QgsProcessing.TypeVector],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.projectLocation,
                "Folder for Run Outputs",
                createByDefault=True,
                defaultValue=None,
            )
        )
        param = QgsProcessingParameterEnum(
            "DualSoils",
            "Treat Dual Category Soils as",
            optional=False,
            options=["Undrained [Default]", "Drained", "Average"],
            allowMultiple=False,
            defaultValue=[0],
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        lookup_layer = extract_lookup_table(self, parameters, context)
        if lookup_layer is None:
            feedback.reportError(
                "Land Use Lookup Table must be provided with Custom Land Use Type.\n",
                True,
            )
            return {}

        # R-factor - rainfall
        rainfall_raster = self.parameterAsRasterLayer(
            parameters, self.rainfallRaster, context
        )

        # K-factor - soil erodability
        erodability_raster = self.fill_zero_k_factor_cells(
            parameters, outputs, feedback, context
        )

        # C-factor - land cover
        c_factor_raster = self.create_c_factor_raster(
            lookup_layer=lookup_layer,
            parameters=parameters,
            context=context,
            feedback=feedback,
            outputs=outputs,
        )

        # LS-factor - length-slope
        feedback.reportError("ls-factor")
        # length_slope_raster = self.create_length_slope_raster(
        #     parameters, outputs, results, context, feedback
        # )

        raster_math_params = {
            "input_a": c_factor_raster,
            "input_b": r"C:\NSPECT\wsdelin\HI_SampleWS\lsgrid.tif",
            "input_c": r"C:\NSPECT\HI_Sample_Data\soilsk1.tif",
            "input_d": r"C:\NSPECT\HI_Sample_Data\HI_rfactor.tif",  # rainfall_raster,
            "band_a": 1,
            "band_b": 1,
            "band_c": 1,
            "band_d": 1,
        }
        perform_raster_math(
            "A*B*C*D",
            raster_math_params,
            context,
            feedback,
            output=r"C:\Users\itodd\Downloads\sample\output.tif",
        )

        ## Sediment Delivery Ratio
        drainage_area = self.get_drainage_area(parameters, context)
        if drainage_area is None:
            feedback.pushError("Invalid Land Use Raster CRS.")
            return {}

        cn = Curve_Number(
            lu_raster=self.parameterAsRasterLayer(
                parameters, self.landUseRaster, context
            ),
            soil_raster=self.parameterAsRasterLayer(
                parameters, self.soilsRasterRaw, context
            ),
            dual_soil_type=0,
            lookup_layer=extract_lookup_table(self, parameters, context),
            context=context,
            feedback=feedback,
        )
        outputs["CN"] = cn.generate_cn_raster()

        return results

    def name(self):
        return "Run Erosion Analysis"

    def displayName(self):
        return "Run Erosion Analysis"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def createInstance(self):
        return RunErosionAnalysis()

    def create_length_slope_raster(self, parameters, outputs, context, feedback):
        # r.watershed
        elevation_raster = self.parameterAsRasterLayer(
            parameters, self.elevationRaster, context
        )
        alg_params = {
            "-4": False,
            "-a": False,
            "-b": False,
            "-m": False,
            "-s": False,
            "GRASS_RASTER_FORMAT_META": "",
            "GRASS_RASTER_FORMAT_OPT": "",
            "GRASS_REGION_CELLSIZE_PARAMETER": 0,
            "GRASS_REGION_PARAMETER": None,
            "blocking": None,
            "convergence": 5,
            "depression": None,
            "disturbed_land": None,
            "elevation": parameters[self.elevationRaster],
            "flow": None,
            "max_slope_length": None,
            "memory": 300,
            "threshold": 500,
            "length_slope": str(self.testOutFolder / "ls.tif"),
        }
        outputs["Rwatershed"] = processing.run(
            "grass7:r.watershed",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        length_slope = outputs["Rwatershed"]["length_slope"]
        return length_slope

    def fill_zero_k_factor_cells(self, parameters, outputs, feedback, context):
        """Zero values in the K-Factor grid should be assumed "urban" and given a default value."""
        raster_layer = self.parameterAsRasterLayer(
            parameters, self.soilsRaster, context
        )
        expression = '(("{0}@1" = 0) * 0.3) + (("{0}@1" > 0) * "{0}@1")'.format(
            raster_layer.name()
        )
        feedback.reportError(expression)
        # Raster calculator
        alg_params = {
            "CELLSIZE": 0,
            "CRS": None,
            "EXPRESSION": expression,
            "EXTENT": None,
            "LAYERS": raster_layer,
            "OUTPUT": str(self.testOutFolder / "kfactor.tif"),
        }
        outputs["RasterCalculator"] = processing.run(
            "qgis:rastercalculator",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        return outputs["RasterCalculator"]["OUTPUT"]

    def create_c_factor_raster(
        self, lookup_layer, parameters, context, feedback, outputs
    ):
        land_use_raster = convert_raster_data_type_to_float(
            raster_layer=self.parameterAsRasterLayer(
                parameters, self.landUseRaster, context
            ),
            context=context,
            feedback=feedback,
            outputs=outputs,
            output=str(self.testOutFolder / "lu_change.tif"),
        )
        c_factor_raster = assign_land_use_field_to_raster(
            lu_raster=land_use_raster,
            lookup_layer=lookup_layer,
            value_field="c_factor",
            context=context,
            feedback=feedback,
            output=str(self.testOutFolder / "c_factor.tif"),
        )["OUTPUT"]
        return c_factor_raster

    def get_drainage_area(self, parameters, context):
        """Returns None if an invalid crs is found."""
        lu_raster = self.parameterAsRasterLayer(parameters, self.landUseRaster, context)
        size_x = lu_raster.rasterUnitsPerPixelX()
        size_y = lu_raster.rasterUnitsPerPixelY()
        # Convert size into square kilometers
        raster_units = lu_raster.dataProvider().mapUnits()
        if raster_units == QgsUnitTypes.AreaSquareKilometers:
            multiplier = 1
        elif raster_units == QgsUnitTypes.AreaSquareMeters:
            multiplier = 1000
        elif raster_units == QgsUnitTypes.AreaSquareMiles:
            multiplier = 0.621371
        elif raster_units == QgsUnitTypes.AreaSquareFeet:
            multiplier = 3280.84
        else:
            return None
        return size_x * size_y * (multiplier ** 2)

    def get_curve_number(self, parameters, context, feedback):
        cn = Curve_Number(
            lu_raster=self.parameterAsRasterLayer(
                parameters, self.landUseRaster, context
            ),
            soil_raster=self.parameterAsRasterLayer(
                parameters, self.soilsRasterRaw, context
            ),
            dual_soil_type=0,
            lookup_layer=extract_lookup_table(self, parameters, context),
            context=context,
            feedback=feedback,
        )

