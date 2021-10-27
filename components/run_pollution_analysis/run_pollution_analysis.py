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


def matrix_to_dict(matrix: list) -> dict:
    matrix_dict = {matrix[i]: matrix[i + 1] for i in range(0, len(matrix), 2)}
    return matrix_dict

def filter_dict(input: dict) -> dict:
    output = dict(input)
    for k, v in input.items():
        if v.lower() not in ['y', 'yes']:
            del output[k]
    return output

class RunPollutionAnalysis(QgsProcessingAlgorithm):
    lookup_tables = {0: "NLCD", 1: "C-CAP"}
    default_lookup_path = r"file:///C:\Users\asiddiqui\Documents\github_repos\QNSPECT\resources\coefficients\{0}.csv"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString('ProjectName', 'Run Name', multiLine=False, optional=True, defaultValue=''))
        self.addParameter(QgsProcessingParameterFile('ProjectLocation', 'Location for Run Output', optional=True,behavior=QgsProcessingParameterFile.Folder, fileFilter='All files (*.*)', defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterLayer('ElevatoinRaster', 'Elevation Raster', optional=True,defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterLayer('SoilRaster', 'Soil Raster', optional=True,defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterLayer('PrecipitationRaster', 'Precipitation Raster', optional=True,defaultValue=None))
        self.addParameter(QgsProcessingParameterEnum('RainUnits', 'Rain Units', options=['Inches','Millimeters'], optional=True,allowMultiple=False, defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('RainyDays', 'Number of Rainy Days in a Year', optional=True,type=QgsProcessingParameterNumber.Integer, minValue=1, maxValue=366, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterLayer('LandUseRaster', 'Land Use Raster', optional=True,defaultValue=None))
        self.addParameter(QgsProcessingParameterEnum('LandUseType', 'Land Use Type', optional=True, options=['NLCD','C-CAP','Custom'], allowMultiple=False, defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('LookupTable', 'Land Use Lookup Table', optional=True, types=[QgsProcessing.TypeVector], defaultValue=None))
        self.addParameter(QgsProcessingParameterEnum('DualSoils', 'Treat Dual Category Soils as', optional=True,options=['Undrained [Default]','Drained','Average'], allowMultiple=False, defaultValue=[0]))
        self.addParameter(QgsProcessingParameterMatrix('SelectOutputs', 'Select Outputs', optional=True,headers=['Name','Output? [Y/N]'], defaultValue=['Runoff','Y','Lead','N','Nitrogen','N','Phosphorus','N','Zinc','N','TSS','N']))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        ## Extract inputs
        land_use_type = self.parameterAsEnum(parameters, 'LandUseType', context)
        desired_outputs = matrix_to_dict(self.parameterAsMatrix(parameters, 'SelectOutputs', context))
        # filter out non Y or Yes
        desired_outputs = filter_dict(desired_outputs)

        ## Assertions
        if land_use_type not in [0,1] and not parameters['LookupTable']:
            feedback.reportError("Land Use Lookup Table must be provided with Custom Land Use Type.\n", True)
            return {}
        elif not parameters['LookupTable']: # create lookup table from default
            lookup_table_layer = QgsVectorLayer(self.default_lookup_path.format(self.lookup_tables[land_use_type]), "Land Use Lookup Table", "delimitedtext")
            parameters['LookupTable'] = lookup_table_layer
        
        
        # temp
        results["lookup"] = parameters["LookupTable"].source()
        results["desired_outputs"] = desired_outputs


        return results

    def name(self):
        return 'Run Pollution Analysis'

    def displayName(self):
        return 'Run Pollution Analysis'

    def group(self):
        return 'QNSPECT'

    def groupId(self):
        return 'QNSPECT'

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
