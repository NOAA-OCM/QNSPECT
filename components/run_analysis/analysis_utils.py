"""
Store common functions that are required by different analysis modules
"""


from qgis.core import QgsProcessing, QgsVectorLayer, Qgis, QgsRasterLayer
import processing
import os
from pathlib import Path

LAND_USE_TABLES = {0: "NLCD", 1: "C-CAP"}
LAND_USE_PATH = (
    f"file:///{Path(__file__).parent.parent.parent / 'resources' / 'coefficients'}"
)


def filter_matrix(matrix: list) -> list:
    matrix_filtered = [
        matrix[i]
        for i in range(0, len(matrix), 2)
        if matrix[i + 1].lower() in ["y", "yes"]
    ]
    return matrix_filtered


def convert_raster_data_type_to_float(
    raster_layer, context, feedback, outputs, output=None
):
    if output is None:
        output = QgsProcessing.TEMPORARY_OUTPUT
    if isinstance(raster_layer, str) and os.path.isfile(raster_layer):
        raster_layer = QgsRasterLayer(f"file:///{raster_layer}", "Raster Convert Layer")
    data_type = raster_layer.dataProvider().dataType(1)
    if data_type not in [Qgis.Float32, Qgis.Float64, Qgis.CFloat32, Qgis.CFloat64]:
        # Rearrange bands
        alg_params = {
            "BANDS": [1],
            "DATA_TYPE": Qgis.Float32,
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


def perform_raster_math(
    exprs, input_dict, context, feedback, output=None,
):
    """Wrapper around QGIS GDAL Raster Calculator"""
    if output is None:
        output = QgsProcessing.TEMPORARY_OUTPUT

    alg_params = {
        "BAND_A": input_dict.get("band_a", None),
        "BAND_B": input_dict.get("band_b", None),
        "BAND_C": input_dict.get("band_c", None),
        "BAND_D": input_dict.get("band_d", None),
        "BAND_E": input_dict.get("band_e", None),
        "BAND_F": input_dict.get("band_f", None),
        "EXTRA": "",
        "FORMULA": exprs,
        "INPUT_A": input_dict.get("input_a", None),
        "INPUT_B": input_dict.get("input_b", None),
        "INPUT_C": input_dict.get("input_c", None),
        "INPUT_D": input_dict.get("input_d", None),
        "INPUT_E": input_dict.get("input_e", None),
        "INPUT_F": input_dict.get("input_f", None),
        "NO_DATA": -9999,
        "OPTIONS": "",
        "RTYPE": 5,
        "OUTPUT": output,
    }
    return processing.run(
        "gdal:rastercalculator",
        alg_params,
        context=context,
        feedback=feedback,
        is_child_algorithm=True,
    )


def assign_land_use_field_to_raster(
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


def extract_lookup_table(alg, parameters, context):
    """Extract the lookup table as a vector layer. Retuns None if the selection was invalid"""
    if parameters[alg.lookupTable]:
        return alg.parameterAsVectorLayer(parameters, alg.lookupTable, context)

    land_use_type = alg.parameterAsEnum(parameters, alg.landUseType, context)
    if land_use_type in [0, 1]:  # create lookup table from default
        return QgsVectorLayer(
            os.path.join(LAND_USE_PATH, f"{LAND_USE_TABLES[land_use_type]}.csv"),
            "Land Use Lookup Table",
            "delimitedtext",
        )
