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


def run_alg_styler(display_name, layer_color1, layer_color2):
    """Create a New Post Processor class and returns it"""
    # Just simply creating a new instance of the class was not working
    # for details see https://gis.stackexchange.com/questions/423650/qgsprocessinglayerpostprocessorinterface-only-processing-the-last-layer
    class LayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
        instance = None
        name = display_name
        color1 = layer_color1
        color2 = layer_color2

        def postProcessLayer(self, layer, context, feedback):
            if layer.isValid():
                layer.setName(self.name)

                prov = layer.dataProvider()
                stats = prov.bandStatistics(
                    1, QgsRasterBandStats.All, layer.extent(), 0
                )
                min = stats.minimumValue
                max = stats.maximumValue
                renderer = QgsSingleBandPseudoColorRenderer(
                    layer.dataProvider(), band=1
                )
                color_ramp = QgsGradientColorRamp(
                    QColor(*self.color1), QColor(*self.color2)
                )
                renderer.setClassificationMin(min)
                renderer.setClassificationMax(max)
                renderer.createShader(color_ramp)
                layer.setRenderer(renderer)

        # Hack to work around sip bug!
        @staticmethod
        def create() -> "LayerPostProcessor":
            LayerPostProcessor.instance = LayerPostProcessor()
            return LayerPostProcessor.instance

    return LayerPostProcessor.create()


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
        "accumulation": output,
    }
    feedback.pushInfo("Input parameters:")
    feedback.pushCommandInfo(str(alg_params))
    return processing.run(
        "grass7:r.watershed",
        alg_params,
        context=context,
        feedback=None,
        is_child_algorithm=True,
    )
