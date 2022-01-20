from pathlib import Path
import sys
import math
import datetime
import json

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

from analysis_utils import (
    extract_lookup_table,
    assign_land_use_field_to_raster,
    perform_raster_math,
    convert_raster_data_type_to_float,
    LAND_USE_TABLES,
    grass_material_transport,
)
from Curve_Number import Curve_Number
from relief_length_ratio import create_relief_length_ratio_raster

DEFAULT_URBAN_K_FACTOR_VALUE = 0.3

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsUnitTypes,
    QgsProcessingParameterString,
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
    mdf = "MDF"
    rusle = "RUSLE"
    sedimentDeliveryRatio = "SedimentDeliveryRatio"
    sedimentYieldLocal = "SedimentLocal"
    sedimentYieldAccumulated = "SedimentAccumulated"
    runName = "RunName"
    dualSoils = "DualSoils"
    loadOutputs = "LoadOutputs"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                self.runName,
                "Run Name",
                multiLine=False,
                optional=False,
                defaultValue="",
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.elevationRaster, "Elevation Raster", defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.rainfallRaster, "R-Factor Raster (Rainfall)", defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.landUseRaster, "Land Use Raster", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.soilsRasterRaw, "Soils Raster", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.soilsRaster, "K-factor Raster (Soils)", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.landUseType,
                "Land Use Type",
                options=list(LAND_USE_TABLES.values()) + ["Custom"],
                allowMultiple=False,
                defaultValue=None,
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
            QgsProcessingParameterBoolean(
                self.loadOutputs,
                "Open output files after running algorithm",
                defaultValue=True,
            )
        )
        param = QgsProcessingParameterEnum(
            self.dualSoils,
            "Treat Dual Category Soils as",
            optional=False,
            options=["Undrained [Default]", "Drained", "Average"],
            allowMultiple=False,
            defaultValue=[0],
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(
            self.mdf, "Use Multi Direction Flow [MDF] Routing", defaultValue=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.projectLocation,
                "Folder for Run Outputs",
                createByDefault=True,
                defaultValue=None,
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        load_outputs: bool = self.parameterAsBool(parameters, self.loadOutputs, context)

        cell_size_sq_meters = self.cell_size_in_meters(parameters, context)
        if cell_size_sq_meters is None:
            feedback.pushError("Invalid Elevation Raster CRS units.")
            return {}

        lookup_layer = extract_lookup_table(self, parameters, context)
        if lookup_layer is None:
            feedback.reportError(
                "Land Use Lookup Table must be provided with Custom Land Use Type.\n",
                True,
            )
            return {}

        # Folder I/O
        project_loc = Path(
            self.parameterAsString(parameters, self.projectLocation, context)
        )
        run_out_dir: Path = project_loc / self.parameterAsString(
            parameters, self.runName, context
        )
        run_out_dir.mkdir(parents=True, exist_ok=True)

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

        watershed = WatershedCalculator(self, parameters, context, feedback, outputs)

        rusle = self.run_rusle(
            c_factor=c_factor_raster,
            ls_factor=watershed.lsFactor,
            erodability=erodability_raster,
            cell_size_sq_meters=cell_size_sq_meters,
            parameters=parameters,
            context=context,
            feedback=feedback,
            outputs=outputs,
        )

        ## Sediment Delivery Ratio
        rl_raster = create_relief_length_ratio_raster(
            dem_raster=watershed.dem,
            cell_size_sq_meters=cell_size_sq_meters,
            output=r"C:\Projects\work\nspect\workspace\scenarios\New folder\rl_raster.tif",
            context=context,
            feedback=feedback,
            outputs=outputs,
        )

        cn = Curve_Number(
            parameters[self.landUseRaster],
            parameters[self.soilsRasterRaw],
            dual_soil_type=self.parameterAsEnum(parameters, self.dualSoils, context),
            lookup_layer=extract_lookup_table(self, parameters, context),
            context=context,
            feedback=feedback,
        )
        cn.generate_cn_raster()

        sdr = self.run_sediment_delivery_ratio(
            cell_size_sq_meters=cell_size_sq_meters,
            relief_length=rl_raster,
            curve_number=cn.cn_raster,
            parameters=parameters,
            context=context,
            feedback=feedback,
            outputs=outputs,
        )

        sediment_local = str(run_out_dir / (self.sedimentYieldLocal + ".tif"))
        self.run_sediment_yield(
            sediment_delivery_ratio=sdr,
            rusle=rusle,
            context=context,
            feedback=feedback,
            parameters=parameters,
            outputs=outputs,
            results=results,
            output=sediment_local,
        )
        if load_outputs:
            self.handle_post_processing(
                sediment_local, "Local Accumulation (kg)", context
            )

        sediment_acc = str(run_out_dir / (self.sedimentYieldAccumulated + ".tif"))
        acc_results = self.run_sediment_yield_accumulated(
            sediment_yield=sediment_local,
            watershed=watershed,
            context=context,
            feedback=feedback,
            outputs=outputs,
            results=results,
            output=sediment_acc,
        )
        if load_outputs:
            self.handle_post_processing(
                acc_results, "Sediment Accumulation (Mg)", context
            )

        self.create_config_file(
            parameters=parameters,
            context=context,
            results=results,
            project_loc=project_loc,
        )

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

    def fill_zero_k_factor_cells(self, parameters, outputs, feedback, context):
        """Zero values in the K-Factor grid should be assumed "urban" and given a default value."""
        input_dict = {"input_a": parameters[self.soilsRaster], "band_a": 1}
        expr = "((A == 0) * 0.3) + ((A > 0) * A)"
        outputs["KFill"] = perform_raster_math(
            exprs=expr, input_dict=input_dict, context=context, feedback=feedback,
        )
        return outputs["KFill"]["OUTPUT"]

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
            output=QgsProcessing.TEMPORARY_OUTPUT,
        )
        c_factor_raster = assign_land_use_field_to_raster(
            lu_raster=land_use_raster,
            lookup_layer=lookup_layer,
            value_field="c_factor",
            context=context,
            feedback=feedback,
            output=QgsProcessing.TEMPORARY_OUTPUT,
        )["OUTPUT"]
        return c_factor_raster

    def cell_size_in_meters(self, parameters, context):
        """Converts the cell size of the DEM into meters.
        Returns None if the input raster's CRS is not usable."""
        dem = self.parameterAsRasterLayer(parameters, self.elevationRaster, context)
        size_x = dem.rasterUnitsPerPixelX()
        size_y = dem.rasterUnitsPerPixelY()
        area = size_x * size_y
        # Convert size into square kilometers
        raster_units = dem.crs().mapUnits()
        if raster_units == QgsUnitTypes.AreaSquareMeters:
            return area
        elif raster_units == QgsUnitTypes.AreaSquareKilometers:
            return area * 1_000_000.0
        elif raster_units == QgsUnitTypes.AreaSquareMiles:
            return area * 2_589_988.0
        elif raster_units == QgsUnitTypes.AreaSquareFeet:
            return area * 0.09290304

    def run_sediment_delivery_ratio(
        self,
        cell_size_sq_meters: float,
        relief_length,
        curve_number,
        parameters,
        context,
        feedback,
        outputs,
    ):
        """Runs a raster calculator using QGIS's native raster calculator class.
        GDAL does not allow float^float operations, so 'perform_raster_math' cannot be used here."""
        expr = " * ".join(
            [
                "1.366",
                "(10 ^ -11)",
                f"({(math.sqrt(cell_size_sq_meters) / 1_000.0) ** 2} ^ -0.0998)",  # convert to sq km
                f'("{Path(relief_length).stem}@1" ^ 0.3629)',
                f'("{Path(curve_number).stem}@1" ^ 5.444)',
            ]
        )
        alg_params = {
            "EXPRESSION": expr,
            "LAYERS": [relief_length, curve_number],
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        }
        output = outputs[self.sedimentDeliveryRatio] = processing.run(
            "qgis:rastercalculator",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        return output["OUTPUT"]

    def run_sediment_yield(
        self,
        sediment_delivery_ratio,
        rusle,
        context,
        feedback,
        parameters,
        outputs,
        results,
        output,
    ):
        input_dict = {
            "input_a": sediment_delivery_ratio,
            "band_a": 1,
            "input_b": rusle,
            "band_b": 1,
        }
        exprs = "A * B * 907.18474"
        outputs[self.sedimentYieldLocal] = perform_raster_math(
            exprs=exprs,
            input_dict=input_dict,
            context=context,
            feedback=feedback,
            output=output,
        )
        results[self.sedimentYieldLocal] = outputs[self.sedimentYieldLocal]["OUTPUT"]

    def run_sediment_yield_accumulated(
        self,
        sediment_yield,
        watershed: "WatershedCalculator",
        context,
        feedback,
        outputs,
        results,
        output,
    ):
        gmt = outputs[self.sedimentYieldAccumulated] = grass_material_transport(
            elevation=watershed.dem,
            weight=sediment_yield,
            context=context,
            feedback=feedback,
            output=output,
            mfd=watershed.mdf,
        )
        result = gmt["accumulation"]
        results[self.sedimentYieldAccumulated] = result
        return result

    def run_rusle(
        self,
        c_factor,
        ls_factor,
        erodability,
        cell_size_sq_meters,
        parameters,
        context,
        feedback,
        outputs,
    ):
        ## Unit conversion in this function:
        ## -- A * B * C * D yields tons / acre
        ## -- multiply by 0.0002 to convert from acres to meters
        cell_size_acres = cell_size_sq_meters * 0.000247104369
        raster_math_params = {
            "input_a": c_factor,
            "input_b": ls_factor,
            "input_c": erodability,  # k-factor
            "input_d": parameters[self.rainfallRaster],  # rainfall_raster,
            "band_a": 1,
            "band_b": 1,
            "band_c": 1,
            "band_d": 1,
        }
        outputs[self.rusle] = perform_raster_math(
            f"A * B * C * D * {cell_size_acres}",
            raster_math_params,
            context,
            feedback,
            output=QgsProcessing.TEMPORARY_OUTPUT,
        )
        return outputs[self.rusle]["OUTPUT"]

    def create_config_file(
        self, parameters, context, results, project_loc: Path,
    ):
        lookup_layer = extract_lookup_table(self, parameters, context)
        config = {}
        config["Inputs"] = parameters
        config["Inputs"][self.elevationRaster] = self.parameterAsRasterLayer(
            parameters, self.elevationRaster, context
        ).source()
        config["Inputs"][self.landUseRaster] = self.parameterAsRasterLayer(
            parameters, self.landUseRaster, context
        ).source()
        config["Inputs"][self.soilsRaster] = self.parameterAsRasterLayer(
            parameters, self.soilsRaster, context
        ).source()
        config["Inputs"][self.soilsRasterRaw] = self.parameterAsRasterLayer(
            parameters, self.soilsRasterRaw, context
        ).source()
        config["Inputs"][self.rainfallRaster] = self.parameterAsRasterLayer(
            parameters, self.rainfallRaster, context
        ).source()
        if parameters[self.lookupTable]:
            config["Inputs"][self.lookupTable] = lookup_layer.source()
        config["Outputs"] = results
        config["RunTime"] = str(datetime.datetime.now())
        run_name: str = self.parameterAsString(parameters, self.runName, context)
        config_file = project_loc / f"{run_name}.ero.json"
        json.dump(config, config_file.open("w"), indent=4)

    def handle_post_processing(self, layer, display_name, context):
        layer_details = context.LayerDetails(
            display_name, context.project(), display_name
        )
        # layer_details.setPostProcessor(self.grouper)
        context.addLayerToLoadOnCompletion(
            layer, layer_details,
        )


class WatershedCalculator:
    """Class for calculating and holding GRASS Watershed outputs"""

    def __init__(self, alg, parameters, context, feedback, outputs: dict) -> None:
        self.alg: RunErosionAnalysis = alg
        self.parameters = parameters
        self.context = context
        self.feedback = feedback
        self.outputs = outputs
        self.mdf: bool = alg.parameterAsBool(parameters, alg.mdf, context)
        self._run_watershed()

    def _run_watershed(self):
        if self.mdf:
            self.dem = self.parameters[self.alg.elevationRaster]
        else:
            self.dem = self._fill_elevation_depression()

        alg_params = {
            "-4": False,
            "-a": True,
            "-b": False,
            "-m": False,
            "-s": not self.mdf,
            "GRASS_RASTER_FORMAT_META": "",
            "GRASS_RASTER_FORMAT_OPT": "",
            "GRASS_REGION_CELLSIZE_PARAMETER": 0,
            "GRASS_REGION_PARAMETER": None,
            "blocking": None,
            "convergence": 5,
            "depression": None,
            "disturbed_land": None,
            "elevation": self.dem,
            "flow": None,
            "max_slope_length": None,
            "memory": 300,
            "threshold": 500,
            "accumulation": QgsProcessing.TEMPORARY_OUTPUT,
            "length_slope": QgsProcessing.TEMPORARY_OUTPUT,
            "drainage": QgsProcessing.TEMPORARY_OUTPUT,
            "slope_steepness": QgsProcessing.TEMPORARY_OUTPUT,
        }
        self.outputs["RWatershed"] = processing.run(
            "grass7:r.watershed",
            alg_params,
            context=self.context,
            feedback=self.feedback,
            is_child_algorithm=True,
        )
        self.lsFactor = self.outputs["RWatershed"]["length_slope"]
        self.flowDirection = self.outputs["RWatershed"]["drainage"]
        self.accumulation = self.outputs["RWatershed"]["accumulation"]
        self.slope = self.outputs["RWatershed"]["slope_steepness"]

    def _fill_elevation_depression(self):
        # r.fill.dir
        alg_params = {
            "-f": False,
            "GRASS_RASTER_FORMAT_META": "",
            "GRASS_RASTER_FORMAT_OPT": "",
            "GRASS_REGION_CELLSIZE_PARAMETER": 0,
            "GRASS_REGION_PARAMETER": None,
            "format": 0,
            "input": self.parameters[self.alg.elevationRaster],
            "areas": QgsProcessing.TEMPORARY_OUTPUT,
            "direction": QgsProcessing.TEMPORARY_OUTPUT,
            "output": QgsProcessing.TEMPORARY_OUTPUT,
        }
        self.outputs["DEMFill"] = processing.run(
            "grass7:r.fill.dir",
            alg_params,
            context=self.context,
            feedback=self.feedback,
            is_child_algorithm=True,
        )
        return self.outputs["DEMFill"]["output"]
