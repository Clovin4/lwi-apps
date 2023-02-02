import os, h5py
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point, Polygon
import holoviews as hv
hv.extension('plotly')

class Simulation():

    def getObservedSimulatedMap(hdf_loc, gageVector, observed_csv):
        """
        This function will read in the hdf file, gage vector, and observed csv and return the observed and simulated dataframes
        """
        # read in the gage vector
        gageVector=gpd.read_file(gageVector)
        # check that the gage vector has a SITE_ID column
        assert 'SITE_ID' in gageVector.columns, 'The gage vector does not have a SITE_ID column'
        # read in the hdf file
        hdfFile = h5py.File(hdf_loc, 'r')
        # get the area name
        area = hdfFile['Geometry']['2D Flow Areas']['Attributes']
        areaName = str(area['Name'][0]).split("'")[1]
        # get the cells from the hdf file
        cells_hdf = hdfFile['Geometry']['2D Flow Areas'][areaName]['Cells Center Coordinate']
        cells = pd.DataFrame(np.array(cells_hdf))
        cells = cells.rename(columns={0: 'x', 1: 'y'})
        cells['cell'] = cells.index
        # convert the cells to a geodataframe
        cells=gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.x, cells.y), crs='EPSG:6479')
        # convert the gage vector to the same crs as the cells
        gageVector=gageVector.to_crs('EPSG:6479')
        # get the nearest cell for each gage
        gage_df=gpd.sjoin_nearest(gageVector, cells[['cell', 'geometry']])
        # filter the gage_df to only include the gage id and cell number
        gage_df = gage_df[['SITE_ID', 'cell', 'geometry']]
        # get the plan information from the hdf file
        planInfo_hfd = hdfFile['Plan Data']['Plan Information'].attrs
        # convert the plan information to a pandas series
        planInfo= pd.Series(planInfo_hfd).map(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x)
        # get the start and end time from the plan information
        start=planInfo['Simulation Start Time']
        end=planInfo['Simulation End Time']
        # create a time interval from the start and end time
        timeInterval = pd.date_range(start=start, end=end, freq='60min').format()
        # read in the observed data
        observed = pd.read_csv(observed_csv, parse_dates=True, index_col=0)
        # get the simulated data from the hdf file
        simulated_hdf = hdfFile['Results']['Unsteady']['Output']['Output Blocks']['Base Output']['Unsteady Time Series']['2D Flow Areas'][areaName]['Water Surface']
        simulated = pd.DataFrame(np.array(simulated_hdf))
        # set the index to the time interval
        simulated.index = timeInterval
        # convert the index to a datetime
        simulated.index = pd.to_datetime(simulated.index)
        # name the index column datetime
        simulated.index.name = 'datetime'
        # filter the rows in gage_df to only include the gages that are in the observed data
        gage_df = gage_df[gage_df.SITE_ID.isin(observed.columns)]
        # filter the coloumns to only include the gage locations
        simulated = simulated[gage_df.cell]
        # match the cell number to the site id and rename the columns
        simulated.columns = gage_df.SITE_ID
        # create a holomap to show the WSE for each site for the observed and simulated data
        gage_map=hv.HoloMap({site: hv.Curve((observed.index, observed[site]), label='Observed') * hv.Curve((simulated.index, simulated[site]), label='Simulated') for site in simulated.columns}, kdims='site')
        # return the observed and simulated dataframes
        return observed, simulated, gage_map

sim = Simulation