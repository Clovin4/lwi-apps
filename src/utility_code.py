import h5py
import numpy as np
import pandas as pd

class RAS_Utility():

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

ras = RAS_Utility()