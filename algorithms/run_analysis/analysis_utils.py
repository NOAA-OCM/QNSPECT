"""
Store common functions that are required by different analysis modules
"""


from qgis.core import (
    QgsProcessing,
    QgsVectorLayer,
    Qgis,
    QgsRasterLayer,
)

import processing


def convert_raster_data_type_to_float(
    raster_layer: QgsRasterLayer,
    context,
    feedback,
    output=None,
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
        return processing.run(
            "gdal:rearrange_bands",
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )["OUTPUT"]
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
