# from qgis.core import QgsProcessing
# from qgis.core import QgsProcessingAlgorithm
# from qgis.core import QgsProcessingMultiStepFeedback
# from qgis.core import QgsProcessingParameterRasterLayer
# from qgis.core import QgsProcessingParameterRasterDestination
# from qgis.core import QgsExpression
# import processing


# class ComparisonAnalysis(QgsProcessingAlgorithm):
#     rasterA = "RasterA"
#     rasterB = "RasterB"
#     rasterDirect = "RasterDirect"
#     rasterPercent = "RasterPercent"
#     expressionDirect = "A - B"
#     expressionPercent = "100 * ((A - B) / A)"

#     def initAlgorithm(self, config=None):
#         self.addParameter(
#             QgsProcessingParameterRasterLayer(
#                 self.rasterA, "Raster Original", defaultValue=None
#             )
#         )
#         self.addParameter(
#             QgsProcessingParameterRasterLayer(
#                 self.rasterB, "Raster Modified", defaultValue=None
#             )
#         )
#         self.addParameter(
#             QgsProcessingParameterRasterDestination(
#                 self.rasterDirect,
#                 "Direct Comparison Output",
#                 createByDefault=True,
#                 defaultValue=None,
#             )
#         )
#         self.addParameter(
#             QgsProcessingParameterRasterDestination(
#                 self.rasterPercent,
#                 "Percent Comparison Output",
#                 createByDefault=True,
#                 defaultValue=None,
#             )
#         )

#     def processAlgorithm(self, parameters, context, model_feedback):
#         # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
#         # overall progress through the model
#         feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
#         results = {}
#         outputs = {}

#         # Raster calculator for direct
#         outputs["RasterCalculatorDirect"] = self.run_comparison(
#             raster_a=parameters[self.rasterA],
#             raster_b=parameters[self.rasterB],
#             raster_output=parameters[self.rasterDirect],
#             expression=self.expressionDirect,
#             feedback=feedback,
#             context=context,
#         )
#         # Raster calculator for percent
#         outputs["RasterCalculatorPercent"] = self.run_comparison(
#             raster_a=parameters[self.rasterA],
#             raster_b=parameters[self.rasterB],
#             raster_output=parameters[self.rasterPercent],
#             expression=self.expressionPercent,
#             feedback=feedback,
#             context=context,
#         )

#         return results

#     def name(self):
#         return "Comparison Analysis"

#     def displayName(self):
#         return "Comparison Analysis"

#     def group(self):
#         return "QNSPECT"

#     def groupId(self):
#         return "QNSPECT"

#     def createInstance(self):
#         return ComparisonAnalysis()

#     def run_comparison(
#         self, raster_a, raster_b, raster_output, expression, feedback, context
#     ):
#         alg_params = {
#             "BAND_A": QgsExpression("1").evaluate(),
#             "BAND_B": QgsExpression("1").evaluate(),
#             "BAND_C": None,
#             "BAND_D": None,
#             "BAND_E": None,
#             "BAND_F": None,
#             "EXTRA": "",
#             "FORMULA": expression,
#             "INPUT_A": raster_a,
#             "INPUT_B": raster_b,
#             "INPUT_C": None,
#             "INPUT_D": None,
#             "INPUT_E": None,
#             "INPUT_F": None,
#             "NO_DATA": None,
#             "OPTIONS": "",
#             "RTYPE": 5,
#             "OUTPUT": raster_output,
#         }
#         return processing.run(
#             "gdal:rastercalculator",
#             alg_params,
#             context=context,
#             feedback=feedback,
#             is_child_algorithm=True,
#         )
