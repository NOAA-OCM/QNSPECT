"""
Store stylers to be used for different algorithms
"""


from qgis.core import (
    QgsRasterBandStats,
    QgsSingleBandPseudoColorRenderer,
    QgsGradientColorRamp,
    QgsProcessingLayerPostProcessorInterface,
)

from qgis.PyQt.QtGui import QColor


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