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

__author__ = "Ian Todd"
__date__ = "2022-02-09"
__copyright__ = "(C) 2022 by NOAA"

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"


import os
import math
import datetime
import json

from pathlib import Path

from qgis.core import (
    QgsProcessing,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsUnitTypes,
    QgsProcessingParameterString,
    QgsProcessingException,
)
import processing

from QNSPECT.processing.algorithms.qnspect_utils import (
    perform_raster_math,
    grass_material_transport,
)
from QNSPECT.processing.algorithms.run_analysis.analysis_utils import (
    reclassify_land_cover_raster_by_table_field,
    convert_raster_data_type_to_float,
    check_raster_values_in_lookup_table,
)
from QNSPECT.processing.algorithms.run_analysis.curve_number import CurveNumber
from QNSPECT.processing.algorithms.run_analysis.relief_length_ratio import (
    create_relief_length_ratio_raster,
)
from QNSPECT.processing.algorithms.run_analysis.qnspect_run_algorithm import (
    QNSPECTRunAlgorithm,
)

DEFAULT_URBAN_K_FACTOR_VALUE = 0.3


class RunErosionAnalysis(QNSPECTRunAlgorithm):
    lookupTable = "LookupTable"
    landCoverType = "LandCoverType"
    soilRaster = "HSGRaster"
    kFactorRaster = "KFactorRaster"
    elevationRaster = "ElevationRaster"
    rFactorRaster = "RFactorRaster"
    landCoverRaster = "LandCoverRaster"
    projectLocation = "ProjectLocation"
    mfd = False  # "MFD"
    rusle = "RUSLE"
    sedimentYieldLocal = "Sediment Local"
    sedimentYieldAccumulated = "Sediment Accumulated"
    runName = "RunName"
    dualSoils = "DualSoils"
    loadOutputs = "LoadOutputs"

    def __init__(self):
        super().__init__()
        self.run_name = ""

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
                self.landCoverRaster, "Land Cover Raster", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.landCoverType,
                "Land Cover Type",
                options=["Custom"] + list(self._land_cover_TABLES.values()),
                allowMultiple=False,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.lookupTable,
                "Land Cover Lookup Table",
                optional=True,
                types=[QgsProcessing.TypeVector],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.elevationRaster,
                "Elevation Raster",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.rFactorRaster,
                "R-Factor Raster",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.soilRaster, "Hydrologic Soils Group Raster", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.kFactorRaster, "K-Factor Raster", defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.loadOutputs,
                "Open output files after running algorithm",
                defaultValue=True,
            )
        )
        # param = QgsProcessingParameterBoolean(
        #     self.mfd,
        #     "Use Multi Flow Direction [MFD] Routing",
        #     defaultValue=False
        # )
        # param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        # self.addParameter(param)

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
        feedback = QgsProcessingMultiStepFeedback(11, model_feedback)
        results = {}
        outputs = {}
        run_dict = {}

        self.load_outputs = self.parameterAsBool(parameters, self.loadOutputs, context)

        elev_raster = self.parameterAsRasterLayer(
            parameters, self.elevationRaster, context
        )
        land_cover_raster = self.parameterAsRasterLayer(
            parameters, self.landCoverRaster, context
        )

        cell_size_sq_meters = self.cell_size_in_sq_meters(elev_raster)

        if cell_size_sq_meters is None:
            raise QgsProcessingException("Invalid Elevation Raster CRS units.")

        lookup_layer = self.extract_lookup_table(parameters, context)

        check_raster_values_in_lookup_table(
            raster=land_cover_raster,
            lookup_table_layer=lookup_layer,
            context=context,
            feedback=feedback,
        )

        # Folder I/O
        project_loc = Path(
            self.parameterAsString(parameters, self.projectLocation, context)
        )
        self.run_name = self.parameterAsString(parameters, self.runName, context)
        run_out_dir: Path = project_loc / self.run_name
        run_out_dir.mkdir(parents=True, exist_ok=True)

        ## RUSLE calculations
        # K-factor - soil erodability
        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Preprocessing K-Factor ...")
        erodability_raster = self.fill_zero_k_factor_cells(
            parameters, feedback, context
        )

        # C-factor - land cover
        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Creating C-Factor ...")
        # All final outputs that are not returned to user should be saved in outputs
        c_factor_raster = outputs["C-Factor"] = self.create_c_factor_raster(
            lookup_layer=lookup_layer,
            land_cover_raster_layer=land_cover_raster,
            context=context,
            feedback=feedback,
        )

        # Length-slope factor
        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Creating LS-Factor ...")
        ls_factor = outputs["LS-Factor"] = self.create_ls_factor(parameters, context)

        # RUSLE Soil Loss calculation
        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Performing RUSLE calculations ...")
        rusle = outputs["RUSLE Soil Loss"] = self.run_rusle(
            c_factor=c_factor_raster,
            ls_factor=ls_factor,
            erodability=erodability_raster,
            cell_size_sq_meters=cell_size_sq_meters,
            parameters=parameters,
            context=context,
            feedback=feedback,
        )

        ## Sediment Delivery Ratio calculation section
        # Relief length ratio part
        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Creating Relief Length Ratio ...")
        rl_raster = outputs["Relief Length Ratio"] = create_relief_length_ratio_raster(
            dem_raster=elev_raster,
            cell_size_sq_meters=cell_size_sq_meters,
            context=context,
            feedback=feedback,
        )

        # Curve number part
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Creating curve numbers ...")
        cn = CurveNumber(
            parameters[self.landCoverRaster],
            parameters[self.soilRaster],
            dual_soil_type=self.parameterAsEnum(parameters, self.dualSoils, context),
            lookup_layer=lookup_layer,
            context=context,
            feedback=feedback,
        )
        cn.generate_cn_raster()
        outputs["Curve Number"] = cn.cn_raster

        # Multiply RL and CN
        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Performing SDR calculations ...")
        sdr = outputs["Sediment Delivery Ratio"] = self.run_sediment_delivery_ratio(
            cell_size_sq_meters=cell_size_sq_meters,
            relief_length=rl_raster,
            curve_number=cn.cn_raster,
            context=context,
            feedback=feedback,
        )

        ## Output results
        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Generating local sediments raster ...")
        sediment_local_path = str(run_out_dir / (self.sedimentYieldLocal + ".tif"))
        sediment_local = self.run_sediment_yield(
            sediment_delivery_ratio=sdr,
            rusle=rusle,
            context=context,
            feedback=feedback,
            output=sediment_local_path,
        )
        # because this is an algorithm output this will go in results as well
        outputs[self.sedimentYieldLocal] = sediment_local
        results[self.sedimentYieldLocal] = sediment_local

        if self.load_outputs:
            self.handle_post_processing(
                "sediment", sediment_local_path, "Sediment Local (kg/year)", context
            )

        feedback.setCurrentStep(9)
        if feedback.isCanceled():
            return {}

        # convert to Mg
        feedback.pushInfo("Generating accumulated sediments raster ...")
        input_params = {
            "input_a": sediment_local,
            "band_a": "1",
        }
        sediments_local_Mg = perform_raster_math(
            "(A / 1000)", input_params, context, feedback
        )["OUTPUT"]

        sediment_acc_path = str(run_out_dir / (self.sedimentYieldAccumulated + ".tif"))
        sediment_acc = self.run_sediment_yield_accumulated(
            sediment_yield=sediments_local_Mg,
            elev_raster=elev_raster,
            mfd=False,  # self.parameterAsBool(parameters, self.mfd, context),
            context=context,
            feedback=feedback,
            output=sediment_acc_path,
        )

        outputs[self.sedimentYieldAccumulated] = sediment_acc
        results[self.sedimentYieldAccumulated] = sediment_acc

        if self.load_outputs:
            self.handle_post_processing(
                "sediment", sediment_acc, "Sediment Accumulation (Mg/year)", context
            )

        feedback.setCurrentStep(10)
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("Creating run configuration file ...")
        run_dict = self.create_config_file(
            parameters=parameters,
            context=context,
            results=results,
            run_out_dir=run_out_dir,
            lookup_layer=lookup_layer,
            elev_raster=elev_raster,
            land_cover_raster=land_cover_raster,
        )

        ## Uncomment following two lines to print debugging info
        # feedback.pushCommandInfo("\n" + str(outputs))
        # feedback.pushCommandInfo("\n" + str(run_dict) + "\n")

        return results

    def name(self):
        return "run_erosion_analysis"

    def displayName(self):
        return self.tr("Run Erosion Analysis")

    def createInstance(self):
        return RunErosionAnalysis()

    def fill_zero_k_factor_cells(self, parameters, feedback, context):
        """Zero values in the K-Factor grid should be assumed "urban" and given a default value."""
        input_dict = {"input_a": parameters[self.kFactorRaster], "band_a": 1}
        expr = "((A == 0) * 0.3) + ((A > 0) * A)"
        return perform_raster_math(
            exprs=expr,
            input_dict=input_dict,
            context=context,
            feedback=feedback,
        )["OUTPUT"]

    def create_c_factor_raster(
        self, lookup_layer, land_cover_raster_layer, context, feedback
    ) -> str:
        """"""
        # The c-factor raster will have floating-point values.
        # If the land cover raster used is an integer type,
        # the assignment process will convert the c-factor values to integers.
        # Converting the land cover raster to floating point type fixes that.
        land_cover_raster = convert_raster_data_type_to_float(
            raster_layer=land_cover_raster_layer,
            context=context,
            feedback=feedback,
            output=QgsProcessing.TEMPORARY_OUTPUT,
        )
        c_factor_raster = reclassify_land_cover_raster_by_table_field(
            lc_raster=land_cover_raster,
            lookup_layer=lookup_layer,
            value_field="c_factor",
            context=context,
            feedback=feedback,
            output=QgsProcessing.TEMPORARY_OUTPUT,
        )["OUTPUT"]
        return c_factor_raster

    def cell_size_in_sq_meters(self, elev_raster):
        """Converts the cell size of the elev_raster into meters.
        Returns None if the input raster's CRS is not usable."""
        size_x = elev_raster.rasterUnitsPerPixelX()
        size_y = elev_raster.rasterUnitsPerPixelY()
        area = size_x * size_y
        # Convert size into square kilometers
        raster_units = elev_raster.crs().mapUnits()
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
        context,
        feedback,
    ) -> str:
        """Runs a raster calculator using QGIS's native raster calculator class.
        Modifies given tif names."""

        # GDAL perform raster math function producing correct results but giving RuntimeWarning in power
        # thus using qgis native raster calculator
        # expression for GDAL Raster math 1.366 * (10**(-11)) * ((({math.sqrt(cell_size_sq_meters)} / 1000.0) ** 2) **(-0.0998)) * (A **0.3629) * (B**5.444)

        relief_length_new = Path(relief_length).with_stem("relief_length").as_posix()
        curve_number_new = Path(curve_number).with_stem("curve_number").as_posix()
        os.rename(relief_length, relief_length_new)
        os.rename(curve_number, curve_number_new)

        expr = " * ".join(
            [
                "1.366",
                "(10 ^ -11)",
                f"({(math.sqrt(cell_size_sq_meters) / 1_000.0) ** 2} ^ -0.0998)",  # convert to sq km
                '("relief_length@1" ^ 0.3629)',
                '("curve_number@1" ^ 5.444)',
            ]
        )
        alg_params = {
            "EXPRESSION": expr,
            "LAYERS": [relief_length_new, curve_number_new],
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        }
        return processing.run(
            "qgis:rastercalculator",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )["OUTPUT"]

    def run_sediment_yield(
        self,
        sediment_delivery_ratio,
        rusle,
        context,
        feedback,
        output,
    ) -> str:
        input_dict = {
            "input_a": sediment_delivery_ratio,
            "band_a": 1,
            "input_b": rusle,
            "band_b": 1,
        }
        exprs = "A * B * 907.18474"  # Multiply by 907.18474 to convert from ton to kg
        return perform_raster_math(
            exprs=exprs,
            input_dict=input_dict,
            context=context,
            feedback=feedback,
            output=output,
        )["OUTPUT"]

    def run_sediment_yield_accumulated(
        self,
        sediment_yield,
        elev_raster,
        mfd,
        context,
        feedback,
        output,
    ) -> str:
        return grass_material_transport(
            elevation=elev_raster,
            weight=sediment_yield,
            context=context,
            feedback=feedback,
            output=output,
            mfd=mfd,
        )["OUTPUT"]

    def run_rusle(
        self,
        c_factor,
        ls_factor,
        erodability,
        cell_size_sq_meters,
        parameters,
        context,
        feedback,
    ) -> str:
        ## Unit conversion in this function:
        ## -- The unit of RUSLE Soil Loss  is ton/acre/year
        ## -- multiply by 0.0002 to convert from sq meters to acres
        cell_size_acres = cell_size_sq_meters * 0.000247104369
        raster_math_params = {
            "input_a": c_factor,
            "input_b": ls_factor,
            "input_c": erodability,  # k-factor
            "input_d": parameters[self.rFactorRaster],  # r-factor_raster,
            "band_a": 1,
            "band_b": 1,
            "band_c": 1,
            "band_d": 1,
        }
        return perform_raster_math(
            f"A * B * C * D * {cell_size_acres}",
            raster_math_params,
            context,
            feedback,
            output=QgsProcessing.TEMPORARY_OUTPUT,
        )["OUTPUT"]

    def create_config_file(
        self,
        parameters,
        context,
        results,
        run_out_dir: Path,
        lookup_layer,
        elev_raster,
        land_cover_raster,
    ) -> dict:
        """Create a config file with the name of the run in the outputs folder.
        Uses the "ero" key word to differentiate it from the results of the pollution analysis."""
        config = {}
        config["Inputs"] = parameters
        config["Inputs"][self.elevationRaster] = elev_raster.source()
        config["Inputs"][self.landCoverRaster] = land_cover_raster.source()
        config["Inputs"][self.kFactorRaster] = self.parameterAsRasterLayer(
            parameters, self.kFactorRaster, context
        ).source()
        config["Inputs"][self.soilRaster] = self.parameterAsRasterLayer(
            parameters, self.soilRaster, context
        ).source()
        config["Inputs"][self.rFactorRaster] = self.parameterAsRasterLayer(
            parameters, self.rFactorRaster, context
        ).source()
        if parameters[self.lookupTable]:
            config["Inputs"][self.lookupTable] = lookup_layer.source()
        config["Outputs"] = results
        config["RunTime"] = str(datetime.datetime.now())
        config["QNSPECTVersion"] = self._version
        config_file = run_out_dir / f"{self.run_name}.ero.json"
        json.dump(config, config_file.open("w"), indent=4)
        return config

    def create_ls_factor(self, parameters, context):
        alg_params = {
            "-4": False,
            "-a": True,
            "-b": False,
            "-m": False,
            "-s": True,
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
            "length_slope": QgsProcessing.TEMPORARY_OUTPUT,
        }
        return processing.run(
            "grass7:r.watershed",
            alg_params,
            context=context,
            feedback=None,
            is_child_algorithm=True,
        )["length_slope"]

    def shortHelpString(self):
        return """<html><body>
<a href="https://www.noaa.gov/">Documentation</a>
<h2>Algorithm Description</h2>
<p>The `Run Erosion Analysis` algorithm estimates annual erosion volume for a given area on per cell and accumulated basis. The volume is calculated using RUSLE and Sediment Delivery Ratio models (see the QNSPECT Technical documentation for details).</p>
<p>The user must provide Elevation, Land Cover, Hydrologic Soil Group, K-Factor, and R-Factor rasters for the area of interest. The user is also optionally required to provide a lookup table that relates different land cover classes in the provided Land Cover raster with Curve Number and C-Factor values.</p>

<h2>Input Parameters</h2>

<h3>Run Name</h3>
<p>Name of the run. The algorithm will create a folder with this name and save all outputs and a configuration file in that folder.</p>

<h3>Land Cover Raster</h3>
<p>Land Cover/Classification raster for the area of interest. The algorithm uses Land Cover Raster and Lookup Table to determine each cell's erosion potential.</p>

<h3>Land Cover Type</h3>
<p>Type of Land Cover raster. If the Land Cover raster is not of type C-CAP or NCLD, select custom for this field and supply a lookup table in the Land Cover Lookup Table field.</p>

<h3>Land Cover Lookup Table [optional]</h3>
<p>Lookup table to relate each land cover class with Curve Number and C-Factor. The user can skip providing a lookup table if the land cover type is not custom; the algorithm will utilize the default lookup table for the land cover type selected in the previous option.</p>
<p>To create a custom lookup table, use `Create Lookup Table Template` tool. The table must contain all land cover classes available in the land cover raster.</p>

<h3>Elevation Raster</h3>
<p>Elevation raster for the area of interest. The CRS can be in any units, but the <span style="color: #ff9800">elevation must be in meters</span>. The algorithm uses elevation data to calculate ratios, flow direction, and flow accumulation throughout a watershed.</p>

<h3>R-Factor Raster</h3>
<p>The rainfall-runoff erosivity factor (R-factor) quantifies the effects of raindrop impacts and reflects the amount and rate of runoff associated with the rain.  R-factor raster data for the coterminous United States and six of the main Hawaiian Islands are available from the NOAA Office for Coastal Management. For areas not covered by these data, a method to calculate R-factor is described in chapter 2 of the USDA Handbook Number 703 (Wischmeier and Smith, 1978)<a href="https://www.ars.usda.gov/ARSUserFiles/64080530/RUSLE/AH_703.pdf">PDF, 21.4 MB</a>.</p>

<h3>Hydrologic Soils Group Raster</h3>
<p>Hydrologic Soil Group raster for the area of interest with following mapping {'A': 1, 'B': 2, 'C': 3, 'D':4, 'A/D':5, 'B/D':6, 'C/D':7, 'W':8, Null: 9}. The soil raster is used to generate runoff estimates using NRCS Curve Number method.</p>

<h3>K-factor Raster</h3>
<p>Soil erodibility raster for the area of interest. The K-factor is used in RUSLE equation.</p>

<h2>Advanced Parameters</h2>

<!--h3 >Use Multi Flow Direction [MFD] Routing</h3-->
<!--p >By default, the Single Flow Direction [SFD] option is used for flow routing. Multi Flow Direction [MFD] routing will be utilized if this option is checked. The algorithm passes these flags to GRASS r.watershed function, which is the computational engine for accumulation calculations</p-->

<h3>Treat Dual Category Soils as</h3>
<p>Certain areas can have dual soil types (A/D, B/D, or C/D). These areas possess characteristics of Hydrologic Soil Group D during undrained conditions and characteristics of Hydrologic Soil Group A/B/C for drained conditions.</p>
<p>In this parameter, the user can specify if these areas should be treated as drained, undrained, or average of both conditions. If the average option is selected, the algorithm will use the average of drained and undrained Curve Number for Sediment Delivery Ratio calculations.</p>

<h2>Outputs</h2>

<h3>Folder for Run Outputs</h3>
<p>The algorithm outputs and configuration file will be saved in this directory in a separate folder.</p>
</body></html>"""
