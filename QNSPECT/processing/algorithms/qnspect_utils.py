"""
Store common functions that are required by different QNSPECT Modules
"""

from qgis.core import (
    QgsRasterBandStats,
    QgsSingleBandPseudoColorRenderer,
    QgsGradientColorRamp,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessing,
)

from qgis.PyQt.QtGui import QColor

from qgis.utils import iface
from qgis.PyQt.QtCore import *

import processing


class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    def __init__(self, display_name, layer_color1, layer_color2):
        super().__init__()
        self.display_name = display_name
        self.layer_color1 = layer_color1
        self.layer_color2 = layer_color2

    def postProcessLayer(self, layer, context, feedback):
        if layer.isValid():
            layer.setName(self.display_name)

            prov = layer.dataProvider()
            stats = prov.bandStatistics(1, QgsRasterBandStats.All, layer.extent(), 0)
            min = stats.minimumValue
            max = stats.maximumValue
            renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), band=1)
            color_ramp = QgsGradientColorRamp(
                QColor(*self.layer_color1), QColor(*self.layer_color2)
            )
            renderer.setClassificationMin(min)
            renderer.setClassificationMax(max)
            renderer.createShader(color_ramp)
            layer.setRenderer(renderer)


def select_group(name: str) -> bool:
    """
    Select group item of a node tree
    """

    view = iface.layerTreeView()
    m = view.model()

    listIndexes = m.match(
        m.index(0, 0),
        Qt.DisplayRole,
        name,
        1,
        Qt.MatchFixedString | Qt.MatchRecursive | Qt.MatchCaseSensitive | Qt.MatchWrap,
    )

    if listIndexes:
        i = listIndexes[0]
        view.selectionModel().setCurrentIndex(i, QItemSelectionModel.ClearAndSelect)
        return True

    else:
        return False


def filter_matrix(matrix: list) -> list:
    matrix_filtered = [
        matrix[i]
        for i in range(0, len(matrix), 2)
        if matrix[i + 1].lower() in ["y", "yes"]
    ]
    return matrix_filtered


def perform_raster_math(
    exprs,
    input_dict,
    context,
    feedback,
    output=QgsProcessing.TEMPORARY_OUTPUT,
) -> dict:
    """Wrapper around QGIS GDAL Raster Calculator"""

    alg_params = {
        "BAND_A": input_dict.get("band_a", None),
        "BAND_B": input_dict.get("band_b", None),
        "BAND_C": input_dict.get("band_c", None),
        "BAND_D": input_dict.get("band_d", None),
        "BAND_E": input_dict.get("band_e", None),
        "BAND_F": input_dict.get("band_f", None),
        "EXTRA": "--overwrite",  # explicity pass overwrite till GDAL/QGIS issues are resolved. Refer Github Issue #38
        "FORMULA": exprs,
        "INPUT_A": input_dict.get("input_a", None),
        "INPUT_B": input_dict.get("input_b", None),
        "INPUT_C": input_dict.get("input_c", None),
        "INPUT_D": input_dict.get("input_d", None),
        "INPUT_E": input_dict.get("input_e", None),
        "INPUT_F": input_dict.get("input_f", None),
        "NO_DATA": -999999,
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


def grass_material_transport(
    elevation,
    weight,
    context,
    feedback,
    mfd=True,
    output=QgsProcessing.TEMPORARY_OUTPUT,
    threshold=500,
) -> dict:
    # r.watershed
    alg_params = {
        "-4": False,
        "-a": True,
        "-b": False,
        "-m": False,
        "-s": not mfd,  # single flow direction
        "GRASS_RASTER_FORMAT_META": "",
        "GRASS_RASTER_FORMAT_OPT": "",
        "GRASS_REGION_CELLSIZE_PARAMETER": 0,
        "GRASS_REGION_PARAMETER": None,
        "blocking": None,
        "convergence": 5,
        "depression": None,
        "disturbed_land": None,
        "elevation": elevation,
        "flow": weight,
        "max_slope_length": None,
        "memory": 300,
        "threshold": threshold,  # can be an input advanced parameter
        "accumulation": QgsProcessing.TEMPORARY_OUTPUT,
    }
    feedback.pushInfo("\nGRASS Input parameters:")
    feedback.pushCommandInfo(str(alg_params))
    grass_accumulation = processing.run(
        "grass7:r.watershed",
        alg_params,
        context=context,
        feedback=None,
        is_child_algorithm=True,
    )["accumulation"]

    # Grass output has 0 values marked as nodata
    # Following is a temporary workaround, refer Github issue #29

    # Fill NoData cells
    alg_params = {
        "BAND": 1,
        "FILL_VALUE": 0,
        "INPUT": grass_accumulation,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    }
    all_filled = processing.run(
        "native:fillnodata",
        alg_params,
        context=context,
        feedback=feedback,
        is_child_algorithm=True,
    )["OUTPUT"]

    # Get back original nodata cells
    input_dict = {
        "input_a": all_filled,
        "band_a": 1,
        "input_b": weight,
        "band_b": 1,
    }
    exprs = "A + ( B * 0)"

    return perform_raster_math(
        exprs, input_dict, context=context, feedback=feedback, output=output
    )
