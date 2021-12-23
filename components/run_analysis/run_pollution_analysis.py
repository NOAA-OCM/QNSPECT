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
    QgsProcessingContext,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingException,
)
from qgis.utils import iface


import processing
import os
from datetime import datetime
from json import dumps
from pathlib import Path

import sys
import os
import inspect

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]
sys.path.append(cmd_folder)
sys.path.append(os.path.dirname(cmd_folder))

from Curve_Number import Curve_Number
from Runoff_Volume import Runoff_Volume
from qnspect_utils import perform_raster_math, grass_material_transport, filter_matrix


# class LayerGrouper(QgsProcessingLayerPostProcessorInterface):
#     project = None
#     group = None

#     def __init__(self, group_name):
#         self.group_name = group_name
#         super().__init__()

#     def postProcessLayer(self, layer, context, feedback):
#         if not self.project:
#             self.project = context.project()
#         if not self.group:
#             root = self.project.instance().layerTreeRoot()
#             self.group = root.addGroup(self.group_name)
#         self.group.addLayer(layer)
#         return {}


# class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
#     def postProcessLayer (self, layer, context, feedback):
#         if layer.isValid():
#             layer.loadNamedStyle('Runoff Local.qml')

class RunPollutionAnalysis(QgsProcessingAlgorithm):
    lookup_tables = {1: "C-CAP", 2: "NLCD"}
    default_lookup_path = f"file:///{Path(__file__).parent.parent.parent / 'resources' / 'coefficients'}"
#     grouper = None

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                "RunName", "Run Name", multiLine=False, optional=False, defaultValue="",
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "ElevatoinRaster",
                "Elevation Raster",
                optional=False,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "SoilRaster", "Soil Raster", optional=False, defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "PrecipRaster",
                "Precipitation Raster",
                optional=False,
                defaultValue=None,
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
                "LandUseRaster", "Land Use Raster", optional=False, defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "LandUseType",
                "Land Use Type",
                options=["Custom", "C-CAP", "NLCD"],
                allowMultiple=False,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                "LookupTable",
                "Land Use Lookup Table [*required with Custom Land Use Type]",
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
        self.addParameter(
            QgsProcessingParameterBoolean(
                "LoadOutputs",
                "Open output files after running algorithm",
                defaultValue=True,
            )
        )
        param = QgsProcessingParameterBoolean(
            "ConcOutputs", "Output Concentration Rasters", defaultValue=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean(
            "MFD", "Use Multi Flow Direction [MFD] Routing", defaultValue=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterEnum(
            "DualSoils",
            "Treat Dual Category Soils as",
            optional=False,
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
        run_dict = {}

        ## Extract inputs
        land_use_type = self.parameterAsEnum(parameters, "LandUseType", context)

        desired_outputs = filter_matrix(
            self.parameterAsMatrix(parameters, "DesiredOutputs", context)
        )
        desired_pollutants = [pol for pol in desired_outputs if pol.lower() != "runoff"]
        dual_soil_type = self.parameterAsEnum(parameters, "DualSoils", context)

        precip_units = self.parameterAsEnum(parameters, "PrecipUnits", context)
        rainy_days = self.parameterAsInt(parameters, "RainyDays", context)

        mfd = self.parameterAsBool(parameters, "MFD", context)
        conc_out = self.parameterAsBool(parameters, "ConcOutputs", context)
        load_outputs = self.parameterAsBool(parameters, "LoadOutputs", context)

        run_name = self.parameterAsString(parameters, "RunName", context)
        proj_loc = self.parameterAsString(parameters, "ProjectLocation", context)

        elev_raster = self.parameterAsRasterLayer(
            parameters, "ElevatoinRaster", context
        )
        soil_raster = self.parameterAsRasterLayer(parameters, "SoilRaster", context)
        lu_raster = self.parameterAsRasterLayer(parameters, "LandUseRaster", context)
        precip_raster = self.parameterAsRasterLayer(parameters, "PrecipRaster", context)

        ## Extract Lookup Table
        if parameters["LookupTable"]:
            lookup_layer = self.parameterAsVectorLayer(
                parameters, "LookupTable", context
            )
        elif land_use_type > 0:  # create lookup table from default
            lookup_layer = QgsVectorLayer(
                f"{self.default_lookup_path}/{self.lookup_tables[land_use_type]}.csv",
                "Land Use Lookup Table",
                "delimitedtext",
            )
        else:
            raise QgsProcessingException(
                "Land Use Lookup Table must be provided with Custom Land Use Type.\n"
            )

        # handle different cases in input matrix and lookup layer
        lookup_fields = {f.name().lower(): f.name() for f in lookup_layer.fields()}

        ## Assertions

        if not desired_outputs:
            feedback.pushWarning("No output desired. \n")
            return {}
        if not all([pol.lower() in lookup_fields.keys() for pol in desired_pollutants]):
            raise QgsProcessingException(
                "One or more of the Pollutants is not a column in the Land Use Lookup Table. Either remove the pollutants from Desired Outputs or provide a custom lookup table with desired pollutants.\n"
                + f"Missing Pollutants:\n{[pol.lower() for pol in desired_pollutants if not pol.lower() in lookup_fields.keys()]}\n"
            )    

        # assert all Raster CRS are same and Raster Pixel Units too

        # Folder I/O
        run_out_dir = os.path.join(proj_loc, run_name)
        os.makedirs(run_out_dir, exist_ok=True)

        # self.grouper = LayerGrouper(run_name)

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
            elev_raster,
            precip_units,
            rainy_days,
            context,
            feedback,
        )
        # not putting (L) in the name because special characs don't go well in file names
        # should be handled in post processor through display name
        if "runoff" in [out.lower() for out in desired_outputs]:
            runoff_output = os.path.join(run_out_dir, f"Runoff Local.tif")
            outputs["Runoff Local"] = runoff_vol.calculate_Q(runoff_output)
            results["Runoff Local"] = outputs["Runoff Local"]["OUTPUT"]
            if load_outputs:
                self.handle_post_processing(outputs["Runoff Local"]["OUTPUT"], "Runoff Local (L)", context)
        else:
            outputs["Runoff Local"] = runoff_vol.calculate_Q()

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
            if load_outputs:
                self.handle_post_processing(outputs[pol + " Local"]["OUTPUT"], f"{pol} Local (mg)", context)

        # Accumulated Runoff Calculation (L)
        if "runoff" in [out.lower() for out in desired_outputs]:
            runoff_output = os.path.join(run_out_dir, f"Runoff Accumulated.tif")
            #see this issue for discussion on nodat value issue https://github.com/Dewberry/QNSPECT/issues/29
            outputs["Runoff Accumulated"] = grass_material_transport(parameters["ElevatoinRaster"], outputs["Runoff Local"]["OUTPUT"], context, feedback, mfd, runoff_output)
            results["Runoff Accumulated"] = outputs["Runoff Accumulated"]["accumulation"]
            if load_outputs:
                self.handle_post_processing(outputs["Runoff Accumulated"]["accumulation"], "Runoff Accumulated (L)", context)
        else:
            outputs["Runoff Accumulated"] = grass_material_transport(parameters["ElevatoinRaster"], outputs["Runoff Local"]["OUTPUT"], context, feedback, mfd)

        # Accumulated Pollutants
        for pol in desired_pollutants:
            # Accumulated Pollutant (mg)
            outputs[pol + "accum_mg"] = grass_material_transport(parameters["ElevatoinRaster"], outputs[pol + " Local"]["OUTPUT"], context, feedback, mfd)
            
            # convert to kg
            input_params = {
                "input_a": outputs[pol + "accum_mg"]["accumulation"],
                "band_a": "1",
            }
            outputs[pol + " Accumulated"] = perform_raster_math(
                "(A / 1000000)",
                input_params,
                context,
                feedback,
                os.path.join(run_out_dir, f"{pol} Accumulated.tif"),
            )            
            results[pol + " Accumulated"] = outputs[pol + " Accumulated"]["OUTPUT"]
            if load_outputs:
                self.handle_post_processing(outputs[pol + " Accumulated"]["OUTPUT"], f"{pol} Accumulated (kg)", context)

        # Concentration Calculations
        if conc_out:
            for pol in desired_pollutants:
                # Concentration Pollutant (mg/L)
                input_params = {
                    "input_a": outputs[pol + "accum_mg"]["accumulation"],
                    "band_a": "1",
                    "input_b": outputs["Runoff Accumulated"]["accumulation"],
                    "band_b": "1",                   
                }
                outputs[pol + " Concentration"] = perform_raster_math(
                    "(A / B)",
                    input_params,
                    context,
                    feedback,
                    os.path.join(run_out_dir, f"{pol} Concentration.tif"),
                )            
                results[pol + " Concentration"] = outputs[pol + " Concentration"]["OUTPUT"]
                if load_outputs:
                    self.handle_post_processing(outputs[pol + " Concentration"]["OUTPUT"], f"{pol} Concentration (mg/L)", context)

        # Configuration file
        run_dict["Inputs"] = parameters
        run_dict["Inputs"]["ElevatoinRaster"] = elev_raster.source()
        run_dict["Inputs"]["LandUseRaster"] = lu_raster.source()
        run_dict["Inputs"]["PrecipRaster"] = precip_raster.source()
        run_dict["Inputs"]["SoilRaster"] = soil_raster.source()
        if parameters["LookupTable"]:
            run_dict["Inputs"]["LookupTable"] = lookup_layer.source()
        run_dict["Outputs"] = results
        run_dict["RunTime"] = str(datetime.now())
        with open(os.path.join(run_out_dir, f"{run_name}.pol.json"), "w") as f:
            f.write(dumps(run_dict, indent=4))

        return results


    def postProcessAlgorithm(self, context, feedback):
        iface.mapCanvas().refreshAllLayers()
        return {}

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

    def handle_post_processing(self, layer, display_name, context):
        
        layer_details = context.LayerDetails(
                display_name, context.project(), display_name
            )
        # layer_details.setPostProcessor(self.grouper)
        context.addLayerToLoadOnCompletion(
            layer,
            layer_details,
        )       

