import h5py
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point, Polygon

class RAS_Utility():
    '''This class contains utility functions for HEC-RAS, this is mostly data scraping tools to interact with the HDF5 files'''

    def get_2d_boundary(hdf_loc, projection_loc):
        with h5py.File(hdf_loc, 'r') as f:
            area_2d = f['Geometry']['2D Flow Areas']['Polygon Points']
            area_2d = np.array(area_2d)
            area_2d = pd.DataFrame(area_2d, columns=['x', 'y'])
            polygon = Polygon(area_2d.values)

        with open(projection_loc, 'r') as proj_file:
            crs = proj_file.read()

        return gpd.GeoDataFrame(index=[0], crs=crs, geometry=[polygon])

    def get_model_paths(model_path):
        try:
            for child in Path(model_path).glob('*.prj'):
                if child.is_file():
                    prj_file=child
        except:
            print('No project file found')

        # read the project file and get the plan file extension
        prj_file_list=(Path.read_text(prj_file).split("\n"))
        plan_list = [f'.{x.split("=")[-1]}' for x in prj_file_list if x.startswith("Plan File=")]

        # find all files whose extension is in plan_list return the full path
        plan_file_list = [x for x in Path(model_path).glob('*') if x.suffix in plan_list and x.stem != 'Backup']

        # create a dictionary of plan names and file paths the name is found in the plan file
        plan_dict = {}
        for plan_file in plan_file_list:
            plan_name = Path.read_text(plan_file).split("\n")[0].split("=")[-1]
            plan_dict[plan_name] = plan_file

        # create a dataframe of plan names and file paths
        plan_df = pd.DataFrame.from_dict(plan_dict, orient='index', columns=['plan_file'])

        # add the plans geometry file to plan_df
        plan_df['geom_file'] = plan_df['plan_file'].apply(lambda x: Path.read_text(x).split("\n")[4].split("=")[-1])

        # use glob to find the geometry file
        plan_df['geom_file'] = plan_df['geom_file'].apply(lambda x: [y for y in Path(model_path).glob(f'*{prj_file.stem}.{x}')][0])

        # add hdf file extension to geom_file if it exists
        plan_df['geom_file_hdf'] = plan_df['geom_file'].apply(lambda x: Path(f'{x}.hdf') if Path(f'{x}.hdf').exists() else None)

        # add hdf file extension to plan_file if it exists
        plan_df['plan_file_hdf'] = plan_df['plan_file'].apply(lambda x: Path(f'{x}.hdf') if Path(f'{x}.hdf').exists() else None)

        plan_df.index=plan_df.index.str.replace(' ','_').str.lower()

        return plan_df

    def get_structure_attrs(hdf_loc):
        with h5py.File(hdf_loc, 'r') as f:
            struct_attrs = f['Geometry']['Structures']['Attributes']
            struct_attrs_df = np.array(struct_attrs)
            struct_attrs_df = pd.DataFrame(struct_attrs_df)

            temp_df = struct_attrs_df.select_dtypes([object])
            temp_df = temp_df.stack().str.decode('utf-8').unstack()

            for col in temp_df:
                struct_attrs_df[col] = temp_df[col]

            struct_attrs_df.columns=struct_attrs_df.columns.str.replace(' ','_').str.lower()

        return struct_attrs_df

    def get_sim_data(hdf_loc):
        # creates variable of hdf file that will be read
        with h5py.File(hdf_loc, 'r') as f:

            # sets path within hdf file to find simulation window
            hdfplan_general = f['Plan Data']['Plan Information'].attrs

            # converts plan infomration to pandas series
            # planDatageneral = pd.Series(hdfplan_general).map(lambda st: st.decode('UTF-8'))
            # this will not work for models run with adjusted time step
            # this will convert paln info to pandas series and decode b strings while skiping integers and floats and shit 
            planDatageneral = pd.Series(hdfplan_general).map(lambda x: x.decode('UTF-8') if isinstance(x, bytes) else x)


            # sets path within hdf file to find geometry information
            hdfpaln_geometryData = f['Geometry']['2D Flow Areas']['Attributes']

            # converts 2D Flow Area Information to dataframe
            planDataGeometry = np.array(hdfpaln_geometryData)
            planDataGeometry = pd.DataFrame(planDataGeometry)

            # assign cell count to variable
            cell_count = int(planDataGeometry['Cell Count'])

            # "picks" the 2D Area name out of the geometry data
            geometry_2DName = str(planDataGeometry['Name'][0]).split("'")[1]

            # sets path within hdf file to find the computed timestamps and timesteps in the computation block
            hdfplan_OutTimeDateStamp = f['Results']['Unsteady']['Output']['Output Blocks']['Computation Block']['Global']['Time Date Stamp (ms)']
            hdfplan_OutTimeDateStep = f['Results']['Unsteady']['Output']['Output Blocks']['DSS Hydrograph Output']['Unsteady Time Series']['Time Step']

            # converts plan infomration to pandas dataframe
            planDataOutTimeDateStamp = pd.Series(hdfplan_OutTimeDateStamp).map(lambda x: x.decode('ascii'))

            # convert decoded series to dataframe
            planDataOutTimeDateStamp_df = planDataOutTimeDateStamp.to_frame()

            # converts HEC-RAS's SAS format to a normal fucking timestamp
            planDataOutTimeDateStamp_df[0] = pd.to_datetime(planDataOutTimeDateStamp_df[0], format= "%d%b%Y %H:%M:%S:%f")

            # creat empty list to store the time steps
            timeDiff = [] 

            # iterate through time stamps and compute time steps as integers
            for idx, row in planDataOutTimeDateStamp_df.iterrows():
                try:
                    timeDiffComp = planDataOutTimeDateStamp_df[0][idx] - planDataOutTimeDateStamp_df[0][idx-1]
                    timeDiffComp = int(timeDiffComp.total_seconds())
                    timeDiff.append(timeDiffComp)
                except:
                    timeDiffComp = 0
                    timeDiff.append(timeDiffComp)
            
            # assign time steps to pandas df column
            planDataOutTimeDateStamp_df['Time Step'] = pd.Series(timeDiff)

            # sets path within hdf file to find the 2D Iterations and 2D Itteration Error
            hdfplan_Out2DItterError = f['Results']['Unsteady']['Output']['Output Blocks']['Computation Block']['2D Global']['2D Iteration Error']
            hdfplan_Out2DItter = f['Results']['Unsteady']['Output']['Output Blocks']['Computation Block']['2D Global']['2D Iterations']

            # converts plan infomration to pandas dataframe
            planDataOut2DItterError = pd.DataFrame(hdfplan_Out2DItterError, columns=['Error'])
            planDataOut2DItter = pd.DataFrame(hdfplan_Out2DItter, columns=['Iterations', 'Random Boolean', 'Cell'])

            # create empty dataframe to return extracted values
            runtimeAnalysis_df = pd.DataFrame()

            # assign data and column names to runtime analysis
            runtimeAnalysis_df['time_stamp'] = planDataOutTimeDateStamp_df[0]
            runtimeAnalysis_df['time_step'] = planDataOutTimeDateStamp_df['Time Step']
            runtimeAnalysis_df['iterations'] = planDataOut2DItter['Iterations']
            runtimeAnalysis_df['error'] = planDataOut2DItterError['Error']
            runtimeAnalysis_df['cell'] = planDataOut2DItter['Cell']

            # set cells marked as -1 to null

            runtimeAnalysis_df['cell'].loc[runtimeAnalysis_df['cell'] < 0 ] = np.nan


            # set zero error cells to null
            runtimeAnalysis_df['error'].loc[runtimeAnalysis_df['error'] == 0 ] = np.nan

        return runtimeAnalysis_df

    def get_manning_data(hdf_loc):
        # creates variable of hdf file that will be read
        with h5py.File(hdf_loc, 'r') as f:
            # sets path within hdf file to find simulation window
            manning_data = f['Geometry']['Land Cover (Manning\'s n)']['Calibration Table']

            # converts 2D Flow Area Information to dataframe
            manning_data = np.array(manning_data)
            # convert numpy array to pandas dataframe
            manning_data = pd.DataFrame(manning_data)

            # convert b strings to strings
            temp = manning_data.select_dtypes([object])
            # decode b strings
            temp = temp.stack().str.decode('utf-8').unstack()

            # assign decoded strings to dataframe
            for col in temp:
                manning_data[col] = temp[col]
        return manning_data

    def get_cell_cords(hdf_loc):
        # creates variable of hdf file that will be read
        with h5py.File(hdf_loc, 'r') as f:
            area=f['Geometry']['2D Flow Areas']['Attributes']
            area_name = str(area['Name'][0]).split("'")[1]
            cells=f['Geometry']['2D Flow Areas'][area_name]['Cells Center Coordinate']
            cells=pd.DataFrame(np.array(cells))
            cells=cells.rename(columns={0:'x',1:'y'})
            cells['cell']=cells.index
            cells=cells[['cell','x','y']]
            # hardcode crs for now
            cells=gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.x, cells.y,crs='EPSG:6479'))
        
        return cells
    
    def get_cell_wse(hdf_loc):
        # creates variable of hdf file that will be read
        with h5py.File(hdf_loc, 'r') as f:
            # sets path within hdf file to find the 2D Flow Area Information
            hdfplan_geometryData = f['Geometry']['2D Flow Areas']['Attributes']

            # assigns 2D Flow Area Name to variable
            area_name = str(hdfplan_geometryData['Name'][0]).split("'")[1]

            # assign wse to a dataframe
            wse=f['Results']['Unsteady']['Output']['Output Blocks']['Base Output']['Unsteady Time Series']['2D Flow Areas'][area_name]['Water Surface']
            wse_df=pd.DataFrame(np.array(wse))

        return wse_df

ras = RAS_Utility