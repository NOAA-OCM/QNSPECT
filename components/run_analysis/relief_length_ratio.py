import sys
import math
from pathlib import Path
from qgis.core import QgsUnitTypes, QgsRasterLayer, QgsProcessing
import processing

sys.path.append(str(Path(__file__).parent))
from analysis_utils import perform_raster_math

__all__ = ("create_relief_length_ratio_raster",)


def create_relief_length_ratio_raster(
    dem_raster, cell_size_sq_meters, output, context, feedback, outputs: dict
):
    """Output units in m/km"""
    if not isinstance(dem_raster, QgsRasterLayer):
        dem_raster = QgsRasterLayer(dem_raster, "elevation_layer")
    slope_raster = create_slope(dem_raster, context, feedback)
    return run_raster_calculation(
        slope_raster=slope_raster,
        output=output,
        cell_size_sq_meters=cell_size_sq_meters,
        context=context,
        feedback=feedback,
        outputs=outputs,
    )


def create_slope(dem_raster: QgsRasterLayer, context, feedback):
    # QGIS Native Slope
    alg_params = {
        "INPUT": dem_raster,
        "Z_FACTOR": 1,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    }
    return processing.run(
        "native:slope",
        alg_params,
        context=context,
        feedback=feedback,
        is_child_algorithm=True,
    )["OUTPUT"]


def run_raster_calculation(
    slope_raster, output, cell_size_sq_meters, context, feedback, outputs: dict
):
    ## output in units m/km
    input_dict = {"input_a": slope_raster, "band_a": 1}
    cell_size_meters = math.sqrt(cell_size_sq_meters)

    adjacent_expr = f"( {cell_size_meters} * tan(A * 3.14159 / 180.0) )"  # meters

    expr = f"{adjacent_expr} / {cell_size_meters} / 1000.0"
    outputs["ReliefLengthRaster"] = perform_raster_math(
        exprs=expr,
        input_dict=input_dict,
        context=context,
        feedback=feedback,
        output=output,
    )
    return outputs["ReliefLengthRaster"]["OUTPUT"]

