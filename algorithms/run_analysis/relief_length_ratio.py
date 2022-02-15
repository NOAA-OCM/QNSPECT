import sys
import math
from pathlib import Path
from qgis.core import QgsUnitTypes, QgsRasterLayer, QgsProcessing
import processing

sys.path.append(str(Path(__file__).parent.parent))
from qnspect_alg_utils import perform_raster_math

__all__ = ("create_relief_length_ratio_raster",)


def create_relief_length_ratio_raster(
    dem_raster,
    cell_size_sq_meters,
    context,
    feedback,
) -> str:
    """Relief-length ratio is the ratio between the vertical distance and horizontal distance along a slope.
    This algorithm calculates the height between each cell and its neighbor using the pythagorean theorem.
    It uses the cell slope value and cell size to calculate rise.
    The result is divided by 1000 to yield units of m/km."""
    slope_raster = create_slope(dem_raster, context, feedback)

    input_dict = {"input_a": slope_raster, "band_a": 1}
    cell_size_meters = math.sqrt(cell_size_sq_meters)

    adjacent_expr = f"( {cell_size_meters} * tan(A * 3.14159 / 180.0) )"  # meters

    expr = f"{adjacent_expr} / {cell_size_meters} / 1000.0"
    return perform_raster_math(
        exprs=expr,
        input_dict=input_dict,
        context=context,
        feedback=feedback,
    )["OUTPUT"]


def create_slope(dem_raster: QgsRasterLayer, context, feedback) -> str:
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
