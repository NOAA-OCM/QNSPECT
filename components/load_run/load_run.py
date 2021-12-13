from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile, QgsProcessingException

import processing
import json

class LoadPreviousRun(QgsProcessingAlgorithm):
    load_parameters = {}
    alg = ""

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile('RunFile', 'Run File', behavior=QgsProcessingParameterFile.File, fileFilter='QNSPECT Files (*pol.json *ero.json)', defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        run_file = self.parameterAsString(parameters, "RunFile", context)
        if run_file.lower().endswith(".pol.json"):
            self.alg = "script:Run Pollution Analysis"
        elif run_file.lower().endswith(".ero.json"):
            self.alg = "script:Run Erosion Analysis" 
        else:
            raise QgsProcessingException("Wrong or missing parameter value: Run File")
            
        with open(run_file) as f:
            data = json.load(f)

        self.load_parameters = data["Inputs"]
        
        return results

    def postProcessAlgorithm(self, context, feedback):
        # this can be handled better through QGIS Tasks
        # https://www.opengis.ch/2016/09/07/using-threads-in-qgis-python-plugins/
        # https://www.opengis.ch/2018/06/22/threads-in-pyqgis3/
        processing.execAlgorithmDialog(self.alg, self.load_parameters)
        return {}


    def name(self):
        return 'Load Previous Run'

    def displayName(self):
        return 'Load Previous Run'

    def group(self):
        return 'QNSPECT'

    def groupId(self):
        return 'QNSPECT'

    def createInstance(self):
        return LoadPreviousRun()
