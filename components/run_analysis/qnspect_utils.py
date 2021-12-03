"""
Store common functions that are required by different QNSPECT Modules
"""


from qgis.core import (
    QgsProcessing,
)
import processing


def perform_raster_math(
    exprs,
    input_dict,
    context,
    feedback,
    output=QgsProcessing.TEMPORARY_OUTPUT,
):
    """Wrapper around QGIS GDAL Raster Calculator"""

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

def grass_material_transport(elevation, weight, context, feedback, mfd = True, output=QgsProcessing.TEMPORARY_OUTPUT, threshold = 500):
    feedback.pushWarning(str(mfd))
    # r.watershed
    alg_params = {
        '-4': False,
        '-a': False, 
        '-b': False,
        '-m': False,
        '-s': not mfd, # single flow direction
        'GRASS_RASTER_FORMAT_META': '',
        'GRASS_RASTER_FORMAT_OPT': '',
        'GRASS_REGION_CELLSIZE_PARAMETER': 0,
        'GRASS_REGION_PARAMETER': None,
        'blocking': None,
        'convergence': 5,
        'depression': None,
        'disturbed_land': None,
        'elevation': elevation,
        'flow': weight, 
        'max_slope_length': None,
        'memory': 300,
        'threshold': threshold, # can be an input advanced parameter
        'accumulation': output
    }
    feedback.pushWarning(str(alg_params["-s"]))
    return processing.run('grass7:r.watershed', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
