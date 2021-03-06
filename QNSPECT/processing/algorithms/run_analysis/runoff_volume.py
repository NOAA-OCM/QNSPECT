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
    QgsProcessingMultiStepFeedback,
    QgsRasterLayer,
    QgsDistanceArea,
    QgsCoordinateTransformContext,
    QgsUnitTypes,
    QgsProcessing,
    QgsProcessingContext,
)

from QNSPECT.processing.algorithms.qnspect_utils import perform_raster_math


class RunoffVolume:
    """Class to generate and store Runoff Volume Raster"""

    def __init__(
        self,
        precip_raster: str,
        cn_raster: str,
        ref_raster: QgsRasterLayer,
        precip_units: int,
        raining_days: int,
        context: QgsProcessingContext,
        feedback: QgsProcessingMultiStepFeedback,
    ):
        self.precip_raster = precip_raster
        self.cn_raster = cn_raster
        self.ref_raster = ref_raster
        self.precip_units = precip_units
        self.raining_days = raining_days
        self.context = context
        self.feedback = feedback
        self.outputs = {}

    def preprocess_precipitation(self) -> None:
        if self.precip_units == 1:
            input_params = {
                "input_a": self.precip_raster,
                "band_a": "1",
            }
            self.outputs["P"] = perform_raster_math(
                "A/25.4",
                input_params,
                self.context,
                self.feedback,
            )
            self.precip_raster_in = self.outputs["P"]["OUTPUT"]
        else:
            self.precip_raster_in = self.precip_raster

    def calculate_S(self) -> None:
        """Calculate S (Potential Maximum Retention) (inches)"""
        input_params = {
            "input_a": self.cn_raster,
            "band_a": "1",
        }

        self.outputs["S"] = perform_raster_math(
            # maximum needed here because without it numpy/GDAL is calculating min value as -0
            "numpy.maximum((numpy.divide(1000, A, out=numpy.zeros_like(A), where=(A!=0)) - 10), 0)",
            input_params,
            self.context,
            self.feedback,
        )

    def calculate_Q(self, output=QgsProcessing.TEMPORARY_OUTPUT) -> dict:
        """Calculate runoff volume in Liters"""

        self.preprocess_precipitation()
        self.calculate_S()

        cell_area = (
            self.ref_raster.rasterUnitsPerPixelY()
            * self.ref_raster.rasterUnitsPerPixelX()
        )

        d = QgsDistanceArea()
        tr_cont = QgsCoordinateTransformContext()
        d.setSourceCrs(self.ref_raster.crs(), tr_cont)
        cell_area_sq_feet = d.convertAreaMeasurement(
            cell_area, QgsUnitTypes.AreaSquareFeet
        )

        input_params = {
            "input_a": self.precip_raster,
            "band_a": "1",
            "input_b": self.outputs["S"]["OUTPUT"],
            "band_b": "1",
        }

        ## Volume calculations
        # doing the following calculations in two steps because https://github.com/OSGeo/gdal/issues/5609
        self.outputs["P-Ia"] = perform_raster_math(
            # (Precip-(0.2*S*raining_days))
            f"(A-(0.2*B*{self.raining_days}))",
            input_params,
            self.context,
            self.feedback,
        )

        input_params = {
            "input_a": self.precip_raster,
            "band_a": "1",
            "input_b": self.outputs["S"]["OUTPUT"],
            "band_b": "1",
            "input_c": self.outputs["P-Ia"]["OUTPUT"],
            "band_c": "1",
        }

        # (Volume) (L)
        self.outputs["Q_TEMP"] = perform_raster_math(
            # (((Precip-(0.2*S*raining_days))**2)/(Precip+(0.8*S*raining_days))     *  [If (Precip-0.2S)<0, set to 0]    *  cell area to convert to vol * (28.3168/12) to convert inches to feet and cubic feet to Liters",
            f"((C**2)/(A+(0.8*B*{self.raining_days}))) * (C>0) * {cell_area_sq_feet} * 2.35973722 ",
            input_params,
            self.context,
            self.feedback,
        )

        input_params = {
            "input_a": self.outputs["Q_TEMP"]["OUTPUT"],
            "band_a": "1",
            "input_b": self.cn_raster,
            "band_b": "1",
        }

        # Set Q 0 for CN = 0
        self.outputs["Q"] = perform_raster_math(
            "(B!=0) * A",
            input_params,
            self.context,
            self.feedback,
            output=output,
        )

        self.runoff_vol_raster = self.outputs["Q"]["OUTPUT"]

        return self.outputs["Q"]
