from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterMultipleLayers
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterCrs
from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsMapLayer
import processing
import os

class AlignRasters(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer('TemplateRaster', 'Template Raster', defaultValue=None))
        self.addParameter(QgsProcessingParameterCrs('outputcrs', 'Output CRS', defaultValue='EPSG:4326'))
        self.addParameter(QgsProcessingParameterVectorLayer('watershed', 'Watershed', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        #self.addParameter(QgsProcessingParameterNumber('watershedbuffer', 'Watershed Buffer', optional=True, type=QgsProcessingParameterNumber.Double, minValue=0, defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum('samplemethod', 'Sample Method', options=['Nearest Neighbor','Bilinear','Cubic','Cubic Spline','Lanczos Windowed Sinc','Average','Mode','Maximum','Minimum','Median','First Quartile','Third Quartile'], allowMultiple=False, defaultValue=0))
        self.addParameter(QgsProcessingParameterMultipleLayers('rasterstoalign', 'Rasters to Align', layerType=QgsProcessing.TypeRaster, defaultValue=None))
        self.addParameter(QgsProcessingParameterFile('OutputFolder', 'Output Folder', behavior=QgsProcessingParameterFile.Folder, fileFilter='All files (*.*)', defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        outputs = {}

        watershed = parameters['watershed']
        if isinstance(watershed, str):
            crs = QgsVectorLayer(watershed).crs().toWkt()
        elif isinstance(watershed, (QgsVectorLayer, QgsMapLayer)):
            crs = watershed.crs().toWrt()
            watershed = watershed.source()
        '''
        if parameters['watershedbuffer']:
            feedback.pushInfo('Buffering watershed...')
            amount = parameters['watershedbuffer']
            ws = watershed
            watershed = QgsVectorLayer('Polygon?crs=' + crs, 'temp_buffer', 'memory')
            buffers = [feature.geometry().buffer(amount) for feature in ws.getFeatures()]
            watershed.addFeatures(buffers)
            del buffers
        '''
        
        template = parameters['TemplateRaster']
        if isinstance(template, str):
            template = QgsRasterLayer(template)
        xsize = template.rasterUnitsPerPixelX()
        ysize = template.rasterUnitsPerPixelY()
        if xsize > ysize:
            resolution = ysize
        else:
            resolution = xsize
        
        
        # Warp (reproject)
        for raster in parameters['rasterstoalign']:
            if isinstance(raster, (QgsRasterLayer, QgsMapLayer)):
                raster = raster.source()
            raster_output = os.path.join(parameters['OutputFolder'], os.path.basename(raster))
            while os.path.isfile(raster_output):
                name, ext = os.path.splitext(raster_output)
                raster_output = f'{name}_1{ext}'
            
            alg_params = {
                'DATA_TYPE': 0,
                'EXTRA': '',
                'INPUT': raster,
                'MULTITHREADING': False,
                'NODATA': None,
                'OPTIONS': '',
                'RESAMPLING': parameters['samplemethod'],
                'SOURCE_CRS': None,
                'TARGET_CRS': parameters['outputcrs'],
                'TARGET_EXTENT': parameters['watershed'],
                'TARGET_EXTENT_CRS': None,
                'TARGET_RESOLUTION': None,
                'OUTPUT': raster_output
            }
            processing.run('gdal:warpreproject', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        return results

    def name(self):
        return 'Align Rasters'

    def displayName(self):
        return 'Align Rasters'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return AlignRasters()
