from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterMultipleLayers
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsVectorLayer, QgsFeature
import gdal
import processing
import subprocess
import traceback
import os
from pathlib import Path

RESAMPLES = ['Nearest Neighbor','Bilinear','Cubic','Cubic Spline', 'Lanczos', 'Average', 'Root Mean Square', 'Mode', 'Max', 'Min', 'Median', 'Q1', 'Q3', 'Sum']


def warp_raster(raster: Path, vrt: Path, epsg: str, resample_method: str='bilinear'):
    command = [
        'gdalwarp',
        '-t_srs', f'epsg:{epsg}',
        '-r', resample_method,
        '-of', 'VRT',
        str(vrt),
        str(raster),
    ]
    subprocess.call(command)


def align_raster(template: Path, warp_vrt: Path, align_vrt: Path, resample_method):
    # https://gis.stackexchange.com/questions/333757/aligning-rasters-with-python-qgis
    hDataset = gdal.Open(str(template), gdal.GA_ReadOnly )
    adfGeoTransform = hDataset.GetGeoTransform(can_return_null = True)
    if adfGeoTransform is not None:
        dfGeoXUL = adfGeoTransform[0] 
        dfGeoYUL = adfGeoTransform[3] 
        dfGeoXLR = adfGeoTransform[0] + adfGeoTransform[1] * hDataset.RasterXSize + adfGeoTransform[2] * hDataset.RasterYSize
        dfGeoYLR = adfGeoTransform[3] + adfGeoTransform[4] * hDataset.RasterXSize + adfGeoTransform[5] * hDataset.RasterYSize
        xres = str(abs(adfGeoTransform[1]))
        yres = str(abs(adfGeoTransform[5]))
        subprocess.call(["gdalbuildvrt", '-te', str(dfGeoXUL), str(dfGeoYLR), str(dfGeoXLR), str(dfGeoYUL), "-tr", xres, yres, '-r', resample_method, str(align_vrt), str(warp_vrt)]) 


def clip_raster(align_vrt: Path, clip_vrt: Path, shp: str):
    command = ['gdalwarp', '-cutline', shp,
               '-crop_to_cutline', '-dstalpha',
               align_vrt,
               clip_vrt]
    subprocess.call(command)


def vrt_to_aligned_raster(vrt: Path, raster: Path):
    command = ['gdal_translate', str(vrt), str(raster)]
    subprocess.call(command)


def clean_workspace(workspace: Path):
    for item in workspace.iterdir():
        item.unlink()
    workspace.unlink()


class AlignRasters(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer('TemplateRaster', 'Template Raster', defaultValue=None))
        self.addParameter(QgsProcessingParameterFile('OutputFolder', 'Output Folder', behavior=QgsProcessingParameterFile.Folder, fileFilter='All files (*.*)', defaultValue=None))
        self.addParameter(QgsProcessingParameterMultipleLayers('rasterstoalign', 'Rasters to Align', layerType=QgsProcessing.TypeRaster, defaultValue=None))
        self.addParameter(QgsProcessingParameterEnum('resamplemethod', 'Resample Method', options=RESAMPLES, allowMultiple=False, defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('watershed', 'Watershed', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('watershedbuffer', 'Watershed Buffer', type=QgsProcessingParameterNumber.Double, minValue=0, defaultValue=0))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        outputs = {}

        resample = parameters['resamplemethod']
        if resample == 0:
            resample = 'near'
        else:
            resample = RESAMPLES[resample].lower().replace(' ', '')
            if resample == 'rootmeansquare':
                resample = 'rms'
            elif resample == 'median':
                resample = 'med'

        out_folder = Path(parameters['OutputFolder'])
        workspace = out_folder / 'WORKSPACE'
        if not os.path.isdir(workspace):
            os.mkdir(workspace)
            

        template = Path(str(parameters['TemplateRaster']))
        
        # Buffer the watershed if needed
        watershed = parameters['watershed']
        crs = watershed.crs()
        buffer_amount = parameters['watershedbuffer']
        if buffer_amount:
            temp = QgsVectorLayer(f"Polygon?crs={crs.toWkt()}", "watershed_buffer", "memory")
            ws_data = temp.dataProvider()
            new_features = []
            for feat in watershed.getFeatures():
                geom = feat.geometry()
                buffer = geom.buffer(buffer_amount, 5)
                polygon = buffer.asPolygon()
                new_geom = QgsFeature()
                new_geom.setGeometry(QgsGeometry.fromPolygon(polygon))
                new_features.append(new_geom)
            ws_data.addFeatures(new_features)
            del ws_data
            watershed = temp
            
        
        # Run through each of the rasters
        command = ['gdalbuiltvrt', '-te']
        rasters = parameters['rasterstoalign']
        for raster in rasters:
            path = Path(str(raster))
            out_path = out_folder / path.name
            warp_vrt = workspace / (path.stem + 'w.vrt')
            align_vrt = workspace / (path.stem + 'a.vrt')
            clip_vrt = workspace / (path.stem + 'c.vrt')
            try:
                warp_raster(str(path), warp_vrt, crs.EpsgCrsId, resample)
            except Exception:
                '''TODO: Some warning on warp failure '''
                continue
            try:
                align_raster(template, warp_vrt, align_vrt, resample)
            except Exception:
                '''TODO: Some warning on align failure'''
                continue
            else:
                if align_vrt.is_file():
                    try:
                        clip_raster(align_vrt, clip_vrt, str(watershed))
                    except Exception:
                        '''TODO: some warning that clip failed'''
                    else:
                        vrt_to_aligned_raster(align_vrt, out_path)
                else:
                    ''' TODO: Some warning that align raster failed'''
                    continue
            
            
            
        clean_workspace(workspace)
        #results['Csometestoutputtif'] = outputs['WarpReproject']['OUTPUT']
        #return results

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
