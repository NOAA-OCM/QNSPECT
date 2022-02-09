"""
Store common functions that are required by different analysis modules
"""


from typing import Callable
from qgis.core import (
    QgsProcessing,
    QgsVectorLayer,
    Qgis,
    QgsRasterLayer,
    QgsProcessingException,
)
import processing
import os
from pathlib import Path

LAND_USE_TABLES = {1: "C-CAP", 2: "NLCD"}
LAND_USE_PATH = (
    f"file:///{Path(__file__).parent.parent.parent / 'resources' / 'coefficients'}"
)


def convert_raster_data_type_to_float(
    raster_layer: QgsRasterLayer, context, feedback, outputs, output=None,
):
    """Converts the input raster layer's data type from an integer to a float 32.
    If the input raster's data type is already a float, it will return the input raster layer."""
    if output is None:
        output = QgsProcessing.TEMPORARY_OUTPUT
    data_type = raster_layer.dataProvider().dataType(1)
    if data_type not in [Qgis.Float32, Qgis.Float64, Qgis.CFloat32, Qgis.CFloat64]:
        alg_params = {
            "BANDS": [1],
            "DATA_TYPE": 6,  # Float 32
            "INPUT": raster_layer,
            "OPTIONS": "",
            "OUTPUT": output,
        }
        outputs["RearrangeBands"] = processing.run(
            "gdal:rearrange_bands",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        return outputs["RearrangeBands"]["OUTPUT"]
    return raster_layer


def reclassify_land_use_raster_by_table_field(
    lu_raster: str,
    lookup_layer: QgsVectorLayer,
    value_field: str,
    context,
    feedback,
    output=None,
):
    """Wrapper around QGIS Reclassify by Layer"""
    if output is None:
        output = QgsProcessing.TEMPORARY_OUTPUT

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
        "VALUE_FIELD": value_field,
        "OUTPUT": output,
    }
    return processing.run(
        "native:reclassifybylayer",
        alg_params,
        context=context,
        feedback=feedback,
        is_child_algorithm=True,
    )


def extract_lookup_table(
    parameter_as_vector_layer: Callable,
    parameter_as_enum: Callable,
    parameters,
    context
):
    """Extract the lookup table as a vector layer."""
    if parameters["LookupTable"]:
        return parameter_as_vector_layer(parameters, "LookupTable", context)

    land_use_type = parameter_as_enum(parameters, "LandUseType", context)
    if land_use_type > 0:
        return QgsVectorLayer(
            os.path.join(LAND_USE_PATH, f"{LAND_USE_TABLES[land_use_type]}.csv"),
            "Land Use Lookup Table",
            "delimitedtext",
        )
    else:
        raise QgsProcessingException(
            "Land Use Lookup Table must be provided with Custom Land Use Type.\n"
        )
