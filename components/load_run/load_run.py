from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
import processing

class LoadPreviousRun(QgsProcessingAlgorithm):
    load_parameters = {}

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile('RunFile', 'Run File', behavior=QgsProcessingParameterFile.File, fileFilter='QNSPECT Files (*pol.json *ero.json)', defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}

        return results

    def postProcessAlgorithm(self, context, feedback):
        
        processing.execAlgorithmDialog("native:dropgeometries", self.load_parameters)
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
