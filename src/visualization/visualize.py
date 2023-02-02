import os, h5py
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point, Polygon
import holoviews as hv
hv.extension('plotly')

class Simulation:

    def __init__(self, hdf_loc, gageVector, gageDataCSV):
        self.hdf_loc = hdf_loc
        self.gageVector = gageVector
        self.gageDataCSV = gageDataCSV

    def findGagePoints(self):
        # Associate gage locations with cell from simulation
        gageVector = gpd.read_file(self.gageVector)

        assert 'SITE_ID' in gageVector.columns, "Gage vector must have a column named 'SITE_ID'"

        # Identify hdf file
        self.hdfFile = h5py.File(self.hdf_loc, 'r')

        # Identify the 2D area name
        self.area = self.hdfFile['Geometry']['2D Flow Areas']['Attributes']
        self.areaName = str(self.area['Name'][0]).split("'")[1]

        # Set path to cell locations
        cells_hdf = self.hdfFile['Geometry']['2D Flow Areas'][self.areaName]['Cells Center Coordinate']

        # Create a dataframe of cell locations
        cells = pd.DataFrame(np.array(cells_hdf))

        # rename columns
        cells = cells.rename(columns={0: 'x', 1: 'y'})

        # create a columnm with cell numbers
        cells['cell'] = cells.index

        # create a geometry column
        cells=gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.x, cells.y, crs='EPSG:6479'))

        # create a spatial join between the gage locations and the cell locations
        gage_df = gpd.sjoin_nearest(gageVector, cells[['cell', 'geometry']])

        gage_df = gage_df[['SITE_ID', 'cell', 'geometry']]
        self.gage_df = gage_df
        self.cells = cells

    def readStage(self):

        planInfo_hdf = self.hdfFile['Plan Data']['Plan Information'].attrs

        planInfo = pd.Series(planInfo_hdf).map(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x)

        # Identify the time window
        start=planInfo['Simulation Start Time']
        end=planInfo['Simulation End Time']

        self.timeInterval = pd.date_range(start=start, end=end, freq='60min').format()

        self.observed = pd.read_csv(self.gageDataCSV, parse_dates=True, index_col=0)

        simulated_hdf = self.hdfFile['Results']['Unsteady']['Output']['Output Blocks']['Base Output']['Unsteady Time Series']['2D Flow Areas'][self.areaName]['Water Surface']

        self.simulated = pd.DataFrame(np.array(simulated_hdf))

    def stageHolomap(self):
            
        siteList = self.gage_df['SITE_ID'].tolist()
        cellList = self.gage_df['cell'].tolist()

        self.gage_df = self.gage_df.astype({'Site_ID': 'string', 'cell': 'string'})

        self.gage_df['Subplot_Title'] = self.gage_df['SITE_ID'] + ' ' + self.gage_df['cell']

        observed = self.observed[siteList]
        simulated = self.simulated[cellList]

            # Create a holomap of the observed and simulated stage data
        stage_holomap = hv.HoloMap({site: hv.Curve((self.timeInterval, observed[site]), label='Observed') * hv.Curve((self.timeInterval, simulated[site]), label='Simulated') for site in siteList}, kdims='Site_ID')

        return stage_holomap
