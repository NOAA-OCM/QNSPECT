from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterString,
    QgsProcessingParameterFile,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterMatrix,
    QgsVectorLayer,
)
import processing


def filter_matrix(matrix: list) -> list:
    matrix_filtered = [
        matrix[i]
        for i in range(0, len(matrix), 2)
        if matrix[i + 1].lower() in ["y", "yes"]
    ]
    return matrix_filtered


class RunPollutionAnalysis(QgsProcessingAlgorithm):
    lookup_tables = {0: "NLCD", 1: "C-CAP"}
    default_lookup_path = r"file:///C:\Users\asiddiqui\Documents\github_repos\QNSPECT\resources\coefficients\{0}.csv"
    dual_soil_reclass = {0: [5, 9, 4], 1: [5, 5, 1, 6, 6, 2, 7, 7, 3, 8, 9, 4]}

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                "ProjectName",
                "Run Name",
                multiLine=False,
                optional=True,
                defaultValue="",
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                "ProjectLocation",
                "Location for Run Output",
                optional=True,
                behavior=QgsProcessingParameterFile.Folder,
                fileFilter="All files (*.*)",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "ElevatoinRaster", "Elevation Raster", optional=True, defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "SoilRaster", "Soil Raster", optional=True, defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "DualSoils",
                "Treat Dual Category Soils as",
                optional=True,
                options=["Undrained [Default]", "Drained", "Average"],
                allowMultiple=False,
                defaultValue=[0],
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "PrecipitationRaster",
                "Precipitation Raster",
                optional=True,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "RainUnits",
                "Rain Units",
                options=["Inches", "Millimeters"],
                optional=True,
                allowMultiple=False,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "RainyDays",
                "Number of Rainy Days in a Year",
                optional=True,
                type=QgsProcessingParameterNumber.Integer,
                minValue=1,
                maxValue=366,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "LandUseRaster", "Land Use Raster", optional=True, defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "LandUseType",
                "Land Use Type",
                optional=True,
                options=["NLCD", "C-CAP", "Custom"],
                allowMultiple=False,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                "LookupTable",
                "Land Use Lookup Table",
                optional=True,
                types=[QgsProcessing.TypeVector],
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterMatrix(
                "DesiredOutputs",
                "Desired Outputs",
                optional=True,
                headers=["Name", "Output? [Y/N]"],
                defaultValue=[
                    "Runoff",
                    "Y",
                    "Lead",
                    "N",
                    "Nitrogen",
                    "N",
                    "Phosphorus",
                    "N",
                    "Zinc",
                    "N",
                    "TSS",
                    "N",
                ],
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        ## Extract inputs
        land_use_type = self.parameterAsEnum(parameters, "LandUseType", context)
        desired_outputs = filter_matrix(
            self.parameterAsMatrix(parameters, "DesiredOutputs", context)
        )
        desired_pollutants = [
            pol.lower() for pol in desired_outputs if pol.lower() != "runoff"
        ]
        dual_soil_type = self.parameterAsEnum(parameters, "DualSoils", context)

        ## Extract Lookup Table
        if parameters["LookupTable"]:
            lookup_layer = self.parameterAsVectorLayer(
                parameters, "LookupTable", context
            )
        elif land_use_type in [0, 1]:  # create lookup table from default
            lookup_layer = QgsVectorLayer(
                self.default_lookup_path.format(self.lookup_tables[land_use_type]),
                "Land Use Lookup Table",
                "delimitedtext",
            )
        else:
            feedback.reportError(
                "Land Use Lookup Table must be provided with Custom Land Use Type.\n",
                True,
            )
            return {}
        lookup_fields = [f.name().lower() for f in lookup_layer.fields()]

        ## Assertions
        if not all([pol in lookup_fields for pol in desired_pollutants]):
            feedback.reportError(
                "One or more of the Pollutants is not a column in the Land Use Lookup Table. Either remove the pollutants from Desired Outputs or provide a custom lookup table with desired pollutants. \n",
                True,
            )

        # Convert Soil type 8,9 to 4
        if dual_soil_type in [0, 1]:
            outputs["CleanSoil"] = self.reclass_soil(
                self.dual_soil_reclass[dual_soil_type], parameters, context, feedback
            )
        elif dual_soil_type == 2:
            outputs["SoilUndrain"] = self.reclass_soil(
                self.dual_soil_reclass[0], parameters, context, feedback
            )
            outputs["SoilDrain"] = self.reclass_soil(
                self.dual_soil_reclass[1], parameters, context, feedback
            )

        return results

        # temp
        results["lookup"] = [f.name() for f in lookup_layer.fields()]
        results["desired_outputs"] = desired_outputs
        results["desired_pollutants"] = desired_pollutants

        return results

    def reclass_soil(self, table, parameters, context, feedback):
        alg_params = {
            "DATA_TYPE": 0,
            "INPUT_RASTER": parameters["SoilRaster"],
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
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )

    def name(self):
        return "Run Pollution Analysis"

    def displayName(self):
        return "Run Pollution Analysis"

    def group(self):
        return "QNSPECT"

    def groupId(self):
        return "QNSPECT"

    def shortHelpString(self):
        return """<html><body><h2>Algorithm description</h2>
<p></p>
<h2>Input parameters</h2>
<h3>Run Name</h3>
<p></p>
<h3>Location for Run Output</h3>
<p></p>
<h3>Elevation Raster</h3>
<p></p>
<h3>Soil Raster</h3>
<p></p>
<h3>Treat Dual Category Soils as</h3>
<p></p>
<h3>Precipitation Raster</h3>
<p></p>
<h3>Rain Units</h3>
<p></p>
<h3>Number of Rainy Days in a Year</h3>
<p></p>
<h3>Land Use Raster</h3>
<p></p>
<h3>Land Use Type</h3>
<p></p>
<h3>Land Use Lookup Table</h3>
<p></p>
<h3>Select Outputs</h3>
<p></p>
<br></body></html>"""

    def createInstance(self):
        return RunPollutionAnalysis()
