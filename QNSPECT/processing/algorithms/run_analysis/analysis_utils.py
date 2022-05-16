"""
Store common functions that are required by different analysis modules
"""


from qgis.core import (
    QgsProcessing,
    QgsVectorLayer,
    Qgis,
    QgsRasterLayer,
    QgsProcessingException,
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
        "NO_DATA": -999999,
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


def check_raster_values_in_lookup_table(
    raster,
    lookup_table_layer,
    context,
    feedback,
):
    """Finds the land cover lookup values, then compares with the raster.
    If there area any values in the raster that are not in the lookup table, a QgsProcessingException is raised."""
    lu_codes = set()
    for land_use in lookup_table_layer.getFeatures():
        lu_codes.add(float(land_use["lu_value"]))

    alg_params = {
        "BAND": 1,
        "INPUT": raster,
        "OUTPUT_TABLE": QgsProcessing.TEMPORARY_OUTPUT,
    }
    values_table = processing.run(
        "native:rasterlayeruniquevaluesreport",
        alg_params,
        context=context,
        feedback=feedback,
        is_child_algorithm=True,
    )["OUTPUT_TABLE"]
    values_table_layer = context.takeResultLayer(values_table)

    error_codes = []
    for feature in values_table_layer.getFeatures():
        if feature["value"] not in lu_codes:
            error_codes.append(feature["value"])
    if error_codes:
        raise QgsProcessingException(
            f"The following land cover raster values were not found in the lookup table provided: {', '.join([str(ec) for ec in sorted(error_codes)])}"
        )
