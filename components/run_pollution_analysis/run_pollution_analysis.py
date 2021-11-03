from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterString,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterMatrix,
    QgsVectorLayer,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
)
import processing
import os

import sys

sys.path.append(
    r"C:\Users\asiddiqui\Documents\github_repos\QNSPECT\components\run_pollution_analysis"
)

from Curve_Number import Curve_Number
from Runoff_Volume import Runoff_Volume
from qnspect_utils import perform_raster_math


def filter_matrix(matrix: list) -> list:
    matrix_filtered = [
        matrix[i]
        for i in range(0, len(matrix), 2)
        if matrix[i + 1].lower() in ["y", "yes"]
    ]
    return matrix_filtered


class RunPollutionAnalysis(QgsProcessingAlgorithm):
    lookup_tables = {0: "NLCD", 1: "CCAP"}
    default_lookup_path = r"file:///C:\Users\asiddiqui\Documents\github_repos\QNSPECT\resources\coefficients\{0}.csv"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                "RunName",
                "Run Name",
                multiLine=False,
                optional=True,
                defaultValue="",
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "ElevatoinRaster",
                "Elevation Raster",
                optional=True,
                defaultValue="C:/Users/asiddiqui/Documents/Projects/NSPECT/HI_SAMPLE_TEST_DATA/drived/aligned_DEM.tif",
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "SoilRaster",
                "Soil Raster",
                optional=True,
                defaultValue="C:/Users/asiddiqui/Documents/Projects/NSPECT/HI_SAMPLE_TEST_DATA/drived/HSG.tif",
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "PrecipRaster",
                "Precipitation Raster",
                optional=True,
                defaultValue="C:/Users/asiddiqui/Documents/Projects/NSPECT/HI_SAMPLE_TEST_DATA/drived/precip.tif",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "PrecipUnits",
                "Precipitation Raster Units",
                options=["Inches", "Millimeters"],
                allowMultiple=False,
                defaultValue=[0],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "RainyDays",
                "Number of Rainy Days in a Year",
                type=QgsProcessingParameterNumber.Integer,
                minValue=1,
                maxValue=366,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "LandUseRaster",
                "Land Use Raster",
                optional=True,
                defaultValue="C:/Users/asiddiqui/Documents/Projects/NSPECT/HI_SAMPLE_TEST_DATA/drived/HI_CCAP05.tif",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "LandUseType",
                "Land Use Type",
                options=["NLCD", "C-CAP", "Custom"],
                allowMultiple=False,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                "LookupTable",
                "Land Use Lookup Table",
                optional=True,
                types=[QgsProcessing.TypeVector],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                "DesiredOutputs",
                "Desired Outputs",
                optional=True,
                headers=["Name", "Output? [Y/N]"],
                defaultValue=[
                    "Runoff",
                    "Y",
                    "Lead",
                    "N",
                    "Nitrogen",
                    "N",
                    "Phosphorus",
                    "N",
                    "Zinc",
                    "N",
                    "TSS",
                    "N",
                ],
            )
        )
        param = QgsProcessingParameterBoolean(
            "NoAccuOutputs", "Do not Output Accumulated Rasters", defaultValue=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(
            "MDF", "Use Multi Direction Flow [MDF] Routing", defaultValue=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterEnum(
            "DualSoils",
            "Treat Dual Category Soils as",
            optional=True,
            options=["Undrained [Default]", "Drained", "Average"],
            allowMultiple=False,
            defaultValue=[0],
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                "ProjectLocation",
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

        ## Extract inputs
        land_use_type = self.parameterAsEnum(parameters, "LandUseType", context)
        feedback.pushWarning(str(land_use_type))

        desired_outputs = filter_matrix(
            self.parameterAsMatrix(parameters, "DesiredOutputs", context)
        )
        desired_pollutants = [pol for pol in desired_outputs if pol.lower() != "runoff"]
        dual_soil_type = self.parameterAsEnum(parameters, "DualSoils", context)
        feedback.pushWarning(str(dual_soil_type))

        precip_units = self.parameterAsEnum(parameters, "PrecipUnits", context)
        rainy_days = self.parameterAsInt(parameters, "RainyDays", context)
        feedback.pushWarning(str(rainy_days))

        mfd = self.parameterAsBool(parameters, "MFD", context)
        no_accu_out = self.parameterAsBool(parameters, "NoAccuOutputs", context)

        run_name = self.parameterAsString(parameters, "RunName", context)
        proj_loc = self.parameterAsString(parameters, "ProjectLocation", context)

        elev_raster_layer = self.parameterAsRasterLayer(
            parameters, "ElevatoinRaster", context
        )  # Elevation

        ## Extract Lookup Table
        if parameters["LookupTable"]:
            lookup_layer = self.parameterAsVectorLayer(
                parameters, "LookupTable", context
            )
        elif land_use_type in [0, 1]:  # create lookup table from default
            lookup_layer = QgsVectorLayer(
                self.default_lookup_path.format(self.lookup_tables[land_use_type]),
                "Land Use Lookup Table",
                "delimitedtext",
            )
        else:
            feedback.reportError(
                "Land Use Lookup Table must be provided with Custom Land Use Type.\n",
                True,
            )
            return {}

        # handle different cases in input matrix and lookup layer
        lookup_fields = {f.name().lower(): f.name() for f in lookup_layer.fields()}

        ## Assertions

        if not desired_outputs:
            feedback.pushWarning("No output desired. \n")
            return {}
        if not all([pol.lower() in lookup_fields.keys() for pol in desired_pollutants]):
            feedback.reportError(
                "One or more of the Pollutants is not a column in the Land Use Lookup Table. Either remove the pollutants from Desired Outputs or provide a custom lookup table with desired pollutants. \n",
                True,
            )

        # assert all Raster CRS are same and Raster Pixel Units too

        # Folder I/O
        run_out_dir = os.path.join(proj_loc, run_name)
        os.makedirs(run_out_dir, exist_ok=True)

        ## Generate CN Raster
        cn = Curve_Number(
            parameters["LandUseRaster"],
            parameters["SoilRaster"],
            dual_soil_type,
            lookup_layer,
            context,
            feedback,
        )
        outputs["CN"] = cn.generate_cn_raster()

        # Calculate Q (Runoff) (Liters)
        # using elev layer here because everything should have same units and crs
        runoff_vol = Runoff_Volume(
            parameters["PrecipRaster"],
            outputs["CN"]["OUTPUT"],
            elev_raster_layer,
            precip_units,
            rainy_days,
            context,
            feedback,
        )
        # not putting (L) in the name because special characs don't go well in file names
        # should be handled in post processor through display name
        outputs["Runoff Local"] = runoff_vol.calculate_Q(
            os.path.join(run_out_dir, f"Runoff Local.tif")
        )
        results["Runoff Local"] = outputs["Runoff Local"]["OUTPUT"]

        ## Pollutant rasters
        for pol in desired_pollutants:
            # Calculate pollutant per LU (mg/L)
            outputs[pol + "_lu"] = self.create_pollutant_raster(
                parameters["LandUseRaster"],
                lookup_layer,
                lookup_fields[pol.lower()],
                context,
                feedback,
            )
            # multiply by Runoff Liters to get local effect (mg)
            input_params = {
                "input_a": outputs["Runoff Local"]["OUTPUT"],
                "band_a": "1",
                "input_b": outputs[pol + "_lu"]["OUTPUT"],
                "band_b": "1",
            }
            outputs[pol + " Local"] = perform_raster_math(
                "(A*B)",
                input_params,
                context,
                feedback,
                os.path.join(run_out_dir, f"{pol} Local.tif"),
            )
            results[pol + " Local"] = outputs[pol + " Local"]["OUTPUT"]

        if no_accu_out:
            return results

        # temp
        results["CN"] = outputs["CN"]["OUTPUT"]

        return results

    def name(self):
        return "Run Pollution Analysis"

    def displayName(self):
        return "Run Pollution Analysis"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def shortHelpString(self):
        return """<html><body><h2>Algorithm description</h2>
<p></p>
<h2>Input parameters</h2>
<h3>Run Name</h3>
<p></p>
<h3>Location for Run Output</h3>
<p></p>
<h3>Elevation Raster</h3>
<p></p>
<h3>Soil Raster</h3>
<p></p>
<h3>Treat Dual Category Soils as</h3>
<p></p>
<h3>Precipitation Raster</h3>
<p></p>
<h3>Rain Units</h3>
<p></p>
<h3>Number of Rainy Days in a Year</h3>
<p></p>
<h3>Land Use Raster</h3>
<p></p>
<h3>Land Use Type</h3>
<p></p>
<h3>Land Use Lookup Table</h3>
<p></p>
<h3>Select Outputs</h3>
<p></p>
<br></body></html>"""

    def createInstance(self):
        return RunPollutionAnalysis()

    def create_pollutant_raster(
        self,
        lu_raster: str,
        lookup_layer: QgsVectorLayer,
        pollutant: str,
        context,
        feedback,
    ):
        """Wrapper around QGIS Reclassify by Layer"""
        alg_params = {
            "DATA_TYPE": 5,
            "INPUT_RASTER": lu_raster,
            "INPUT_TABLE": lookup_layer,
            "MAX_FIELD": "lu_value",
            "MIN_FIELD": "lu_value",
            "NODATA_FOR_MISSING": True,
            "NO_DATA": -9999,
            "RANGE_BOUNDARIES": 2,
            "RASTER_BAND": 1,
            "VALUE_FIELD": pollutant,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        }
        return processing.run(
            "native:reclassifybylayer",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
