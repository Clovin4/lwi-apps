import h5py
import numpy as np
import pandas as pd
from pathlib import Path

class RAS_Utility():
    '''This class contains utility functions for HEC-RAS, this is mostly data scraping tools to interact with the HDF5 files'''


    def __init__(self):
        pass

    def get_model_info(self, model_path):
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
        plan_df['geom_file'] = plan_df['geom_file'].apply(lambda x: [y for y in Path(model_path).glob(f'*{x}')][0])

        # add hdf file extension to geom_file if it exists
        plan_df['geom_file_hdf'] = plan_df['geom_file'].apply(lambda x: Path(f'{x}.hdf') if Path(f'{x}.hdf').exists() else None)

        # add hdf file extension to plan_file if it exists
        plan_df['plan_file_hdf'] = plan_df['plan_file'].apply(lambda x: Path(f'{x}.hdf') if Path(f'{x}.hdf').exists() else None)

        return plan_df

    def get_hdf_datasets(self, hdf_loc):
        with h5py.File(hdf_loc, 'r') as f:
            struct_attrs = f['Geometry']['Structures']['Attributes']
            struct_attrs_df = np.array(struct_attrs)
            struct_attrs_df = pd.DataFrame(struct_attrs_df)

            temp_df = struct_attrs_df.select_dtypes([object])
            temp_df = temp_df.stack().str.decode('utf-8').unstack()

            for col in temp_df:
                struct_attrs_df[col] = temp_df[col]

        return struct_attrs_df

    def get_hdf_runtime_data(self, hdf_loc):
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
            runtimeAnalysis_df['Time Stamp'] = planDataOutTimeDateStamp_df[0]
            runtimeAnalysis_df['Time Step'] = planDataOutTimeDateStamp_df['Time Step']
            runtimeAnalysis_df['Iterations'] = planDataOut2DItter['Iterations']
            runtimeAnalysis_df['Error'] = planDataOut2DItterError['Error']
            runtimeAnalysis_df['Cell'] = planDataOut2DItter['Cell']

            # set cells marked as -1 to null

            runtimeAnalysis_df['Cell'].loc[runtimeAnalysis_df['Cell'] < 0 ] = np.nan


            # set zero error cells to null
            runtimeAnalysis_df['Error'].loc[runtimeAnalysis_df['Error'] == 0 ] = np.nan

        return runtimeAnalysis_df

    def get_manning_data(self, hdf_loc):
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

ras = RAS_Utility()