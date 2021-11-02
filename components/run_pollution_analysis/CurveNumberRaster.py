from qgis.core import (
    QgsProcessing,
    QgsVectorLayer,
    QgsProcessingMultiStepFeedback,
)
import processing


class CurveNumberRaster:
    """Class to generate and store Curve Number Raster"""

    outputs = {}
    dual_soil_reclass = {0: [5, 9, 4], 1: [5, 5, 1, 6, 6, 2, 7, 7, 3, 8, 9, 4]}

    def __init__(
        self,
        lu_raster: str,
        soil_raster: str,
        dual_soil_type: int,
        lookup_layer: QgsVectorLayer,
        context,
        feedback: QgsProcessingMultiStepFeedback,
    ):
        self.lookup_layer = lookup_layer
        self.lu_raster = lu_raster
        self.lu_raster = soil_raster
        self.dual_soil_type = dual_soil_type
        self.context = context
        self.feedback = feedback
        self._cn_expression = ""
        self.feedback.reprotError(str(type(context)))

    def generate_cn_exprs(self) -> None:
        """Generate generic CN expression"""
        # Build CN Expression
        cn_calc_expr = []
        for feat in self.lookup_layer.getFeatures():
            lu = feat.attribute("lu_value")
            for i, hsg in enumerate(["a", "b", "c", "d"]):
                cn = feat.attribute(f"cn_{hsg}")
                cn_calc_expr.append(f"logical_and(A=={lu},B=={i+1})*{cn}")

        self._cn_expression = " + ".join(cn_calc_expr)

    def preprocess_soil(self) -> None:
        """Prepare Soil Rasters for CN Generation"""
        ## Preprocess Soil
        if self.dual_soil_type in [0, 1]:
            # replace soil type 5 to 9 per chosen option
            self.outputs["Soil"] = self.reclass_soil(
                self.dual_soil_reclass[self.dual_soil_type]
            )

        elif self.dual_soil_type == 2:
            self.outputs["SoilUndrain"] = self.reclass_soil(self.dual_soil_reclass[0])
            self.outputs["SoilDrain"] = self.reclass_soil(self.dual_soil_reclass[1])

    def generate_cn_raster(self) -> dict:
        """Generate and return CN Raster"""

        self.generate_cn_exprs(self.lookup_layer)

        input_params = {
            "input_a": self.lu_raster,
            "band_a": "1",
        }

        if self.dual_soil_type in [0, 1]:
            input_params.update(
                {
                    "input_b": self.outputs["Soil"]["OUTPUT"],
                    "band_b": "1",
                }
            )
            self.outputs["CN"] = self.perform_raster_math(input_params)

        elif self.dual_soil_type == 2:
            input_params.update(
                {
                    "input_b": self.outputs["SoilUndrain"]["OUTPUT"],
                    "band_b": "1",
                }
            )
            self.outputs["CNUndrain"] = self.perform_raster_math(input_params)

            input_params.update(
                {
                    "input_b": self.outputs["SoilDrain"]["OUTPUT"],
                    "band_b": "1",
                }
            )
            self.outputs["CNDrain"] = self.perform_raster_math(input_params)

            # average undrain and drain CN rasters
            self.outputs["CN"] = self.average_rasters(
                [self.outputs["CNUndrain"]["OUTPUT"], self.outputs["CNDrain"]["OUTPUT"]]
            )

        self.cn_raster = self.outputs["CN"]["OUTPUT"]
        return self.outputs["CN"]

    def reclass_soil(self, table: list):
        """Wrapper around QGIS Reclass by Table Algorithm"""
        alg_params = {
            "DATA_TYPE": 0,
            "INPUT_RASTER": self.soil_raster,
            "NODATA_FOR_MISSING": False,
            "NO_DATA": 255,
            "RANGE_BOUNDARIES": 2,
            "RASTER_BAND": 1,
            "TABLE": table,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        }
        return processing.run(
            "native:reclassifybytable",
            alg_params,
            context=self.context,
            feedback=self.feedback,
            is_child_algorithm=True,
        )
