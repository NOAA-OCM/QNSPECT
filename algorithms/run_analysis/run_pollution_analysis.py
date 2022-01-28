# -*- coding: utf-8 -*-

"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = "Abdul Raheem Siddiqui"
__date__ = "2021-12-29"
__copyright__ = "(C) 2021 by NOAA"

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"

from qgis.core import (
    QgsProcessing,
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
from analysis_utils import (
    extract_lookup_table,
    reclassify_land_use_raster_by_table_field,
)

from QNSPECT.qnspect_algorithm import QNSPECTAlgorithm


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


class RunPollutionAnalysis(QNSPECTAlgorithm):
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
                "SoilRaster",
                "Hydrographic Soils Group Raster",
                optional=False,
                defaultValue=None,
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
        lookup_layer = extract_lookup_table(self, parameters, context)

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
                self.handle_post_processing(
                    outputs["Runoff Local"]["OUTPUT"], "Runoff Local (L)", context
                )
        else:
            outputs["Runoff Local"] = runoff_vol.calculate_Q()

        ## Pollutant rasters
        for pol in desired_pollutants:
            # Calculate pollutant per LU (mg/L)
            outputs[pol + "_lu"] = reclassify_land_use_raster_by_table_field(
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
                self.handle_post_processing(
                    outputs[pol + " Local"]["OUTPUT"], f"{pol} Local (mg)", context
                )

        # Accumulated Runoff Calculation (L)
        if "runoff" in [out.lower() for out in desired_outputs]:
            runoff_output = os.path.join(run_out_dir, f"Runoff Accumulated.tif")
            # see this issue for discussion on nodat value issue https://github.com/Dewberry/QNSPECT/issues/29
            outputs["Runoff Accumulated"] = grass_material_transport(
                parameters["ElevatoinRaster"],
                outputs["Runoff Local"]["OUTPUT"],
                context,
                feedback,
                mfd,
                runoff_output,
            )
            results["Runoff Accumulated"] = outputs["Runoff Accumulated"][
                "accumulation"
            ]
            if load_outputs:
                self.handle_post_processing(
                    outputs["Runoff Accumulated"]["accumulation"],
                    "Runoff Accumulated (L)",
                    context,
                )
        else:
            outputs["Runoff Accumulated"] = grass_material_transport(
                parameters["ElevatoinRaster"],
                outputs["Runoff Local"]["OUTPUT"],
                context,
                feedback,
                mfd,
            )

        # Accumulated Pollutants
        for pol in desired_pollutants:
            # Accumulated Pollutant (mg)
            outputs[pol + "accum_mg"] = grass_material_transport(
                parameters["ElevatoinRaster"],
                outputs[pol + " Local"]["OUTPUT"],
                context,
                feedback,
                mfd,
            )

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
                self.handle_post_processing(
                    outputs[pol + " Accumulated"]["OUTPUT"],
                    f"{pol} Accumulated (kg)",
                    context,
                )

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
                results[pol + " Concentration"] = outputs[pol + " Concentration"][
                    "OUTPUT"
                ]
                if load_outputs:
                    self.handle_post_processing(
                        outputs[pol + " Concentration"]["OUTPUT"],
                        f"{pol} Concentration (mg/L)",
                        context,
                    )

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
        return "run_pollution_analysis"

    def displayName(self):
        return self.tr("Run Pollution Analysis")

    def group(self):
        return self.tr("Analysis")

    def groupId(self):
        return "analysis"

    def shortHelpString(self):
        return """<html><body>
<a href="https://www.noaa.gov/">Documentation</a>
<h2>Algorithm Description</h2>
<p>The `Run Pollution Analysis` algorithm estimates annual runoff volume and pollutant loading for a given area on per cell and accumulated bases. The Runoff Volume is calculated using the NRCS Curve Number method, while pollution loading is calculated using Land Cover as a proxy.</p>
The user must provide Elevation, Land Use, Soil, and Precipitation rasters for the area of interest. The user is also optionally required to provide a lookup table that relates different land use classes in the provided Land Use raster with Curve Number and pollutant loading.
This analysis should be performed on a watershed level to account for all upstream flow at a cell. For accurate results, the area of interest should fully envelop the watershed in consideration.
GRASS `r.watershed`function is used by the algorithm under the hood to calculate runoff and accumulation.</p>
<h2>Input Parameters</h2>
<h3>Run Name</h3>
<p>Name of the run. The algorithm will create a folder with this name and save all outputs and a configuration file in that folder.</p>
<h3>Elevation Raster</h3>
<p>Elevation raster for the area of interest. This can be in any elevation unit. The algorithm only uses elevation data to calculate flow direction and flow accumulation throughout a watershed. </p>
<h3>Soil Raster</h3>
<p>Hydrologic Soil Group raster for the area of interest with following mapping <code>{'A': 1, 'B': 2, 'C': 3, 'D':4, 'A/D':5, 'B/D':6, 'C/D':7, 'W':8, Null: 9}</code>. The soil raster is used to generate runoff estimates using NRCS Curve Number method.</p>
<h3>Precipitation Raster</h3>
<p>Annual precipitation amounts in inches or millimeters for the area of interest. The precipitation values are used to calculate access runoff.</p>
<h3>Precipitation Raster Units</h3>
<p>Units of the precipitation raster, inches or millimeters.</p>
<h3>Number of Rainy Days in a Year</h3>
<p>This field indicates the average number of days rain occurs in one year in the area of interest. A rainy day is a day on which there was enough rain to produce runoff. The higher number of rainy days reduces access runoff volume by increasing retention.</p>
<h3>Land Use Raster</h3>
<p>Land Cover/Classification raster for the area of interest. The algorithm uses Land Use Raster and Lookup Table to determine each cell's runoff and pollution potential.</p>
<h3>Land Use Type</h3>
<p>Type of Land Use raster. If the Land Use raster is not of type C-CAP or NCLD, select custom for this field and supply a lookup table in the `Land Use Lookup Table` field.</p>
<h3>Land Use Lookup Table [optional]</h3>
<p>Lookup table to relate each land use class with Curve Number and pollutant load. The user can skip providing a lookup table if the land use
type is not custom; the algorithm will utilize the default lookup table for the land use type selected in the previous option.
The table must contain all land use classes available in the land use raster and all pollutants that have Output = Y in the `Desired Outputs` parameter.</p>
<h3>Desired Outputs</h3>
<p>In addition to the runoff, the algorithm will output the following rasters for each pollutant added here with Output column as Y:
- Local (per cell) pollutant load [mg]
- Accumulated (all upstream cell) pollutant load [kg]
- Concentration (accumulated pollutant mass divided by accumulated runoff volume) [mg/L]. The concentration raster will only be outputted if the Output Concentration Raster option is checked in Advanced Parameters
The user can add more pollutants here as long as the lookup coefficients for each pollutant are supplied in the land use lookup table.
To exclude an output from the analysis, write N in the Output column. You must click Ok after editing to save your changes.</p>
<h2>Advanced Parameters</h2>
<h3>Output Concentration Raster</h3>
<p>The concentration raster will only be outputted if the Output Concentration Raster option is checked in Advanced Parameters. Default is unchecked.</p>
<h3>Use Multi Flow Direction [MFD] Routing</h3>
<p>By default, the Single Flow Direction [SFD] option is used for flow routing. Multi Flow Direction [MFD] routing will be utilized for the whole analysis if this option is checked. The algorithm passes these flags to GRASS `r.watershed` function, which is the computational engine for runoff direction and accumulation calculations.</p>
<h3>Treat Dual Category Soils as</h3>
<p>Certain areas can have dual soil types (A/D, B/D, or C/D). These areas possess characteristics of Hydrologic Soil Group D during undrained conditions and characterstics of Hydrologic Soil Group A/B/C for drained conditions.</p>
<p>In this parameter, user can specify if these areas should be treated as drained, undrained, or average of both conditions. If the average option is selected, the algorithm will use the average of drained and undrained Curve Number for runoff estimations.</p>
<h2>Outputs</h2>
<h3>Folder for Run Outputs</h3>
<p>The algorithm outputs and configuration file will be saved in this directory in a separate folder.</p>
</body></html>"""

    def createInstance(self):
        return RunPollutionAnalysis()

    def handle_post_processing(self, layer, display_name, context):

        layer_details = context.LayerDetails(
            display_name, context.project(), display_name
        )
        # layer_details.setPostProcessor(self.grouper)
        context.addLayerToLoadOnCompletion(
            layer, layer_details,
        )

