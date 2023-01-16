import h5py
import numpy as np
import pandas as pd

class RAS_Utility():
    '''This class contains utility functions for HEC-RAS, this is mostly data scraping tools to interact with the HDF5 files'''


    def __init__(self):
        pass

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

    # def get_hdf_runtime_data(self, hdf_loc):
    #     with h5py.File(hdf_loc, 'r') as f:
    #         runtime_data = f['Results']['Time Series']['Flow']['Flow Time Series']['Flow Time Series Data']
    #         runtime_data_df = np.array(runtime_data)
    #         runtime_data_df = pd.DataFrame(runtime_data_df)

    #     return runtime_data_df

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
            hdfplan_OutTimeDateStamp = hdfFile['Results']['Unsteady']['Output']['Output Blocks']['Computation Block']['Global']['Time Date Stamp (ms)']
            hdfplan_OutTimeDateStep = hdfFile['Results']['Unsteady']['Output']['Output Blocks']['DSS Hydrograph Output']['Unsteady Time Series']['Time Step']

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
            hdfplan_Out2DItterError = hdfFile['Results']['Unsteady']['Output']['Output Blocks']['Computation Block']['2D Global']['2D Iteration Error']
            hdfplan_Out2DItter = hdfFile['Results']['Unsteady']['Output']['Output Blocks']['Computation Block']['2D Global']['2D Iterations']

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

ras = RAS_Utility()