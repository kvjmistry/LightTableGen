import os
import re
import sys
import glob
import numpy  as np
import pandas as pd
import tables as tb

from invisible_cities.database  import load_db
from invisible_cities.io.dst_io import df_writer

# Takes in the slim file format


# Configure the script here
signal_type = "S2" # S1/S2
detector_db = "next100"
pmt = "PmtR11410"
path_="../files/next100/NEXT100_S2_LT_Step1/"

# Load in the files -- configure the path
column_arr = ["sensor_id", "x", "y", "z"]
index_arr = ["x", "y", "z"]

if signal_type == "S2":
    index_arr = ["x", "y"]
    column_arr = ["sensor_id", "x", "y"]

lt_dir = os.path.expandvars(path_)
lt_filenames = glob.glob(os.path.join(lt_dir, "*.h5"))
lt_filenames = sorted(lt_filenames)
print(lt_filenames)

# Configure the detector database
datapmt = load_db.DataPMT(detector_db, 0)
xpmt, ypmt = datapmt["X"].values, datapmt["Y"].values
sensorids  = datapmt["SensorID"].values

LT  = pd.DataFrame()
ERR = pd.DataFrame()

for i, filename in enumerate(lt_filenames, 0):
    sys.stdout.write(f"Processing file {i}/{len(lt_filenames)} \r")
    sys.stdout.flush()

    # Get the metadata from the files
    config = pd.read_hdf(filename, "LT/Config")
    lt     = pd.read_hdf(filename, "LT/LightTable")

    # Add to the dataframe
    LT  = pd.concat([LT , lt])
    
    # Consolodate the duplicate rows
    LT = LT.groupby(['sensor_id', 'x', 'y', 'z']).agg({'N': 'sum', 'sum': 'sum', 'sum2': 'sum'}).reset_index()

    
# Consolodate the duplicate rows
LT = LT.groupby(['sensor_id', 'x', 'y', 'z']).agg({'N': 'sum', 'sum': 'sum', 'sum2': 'sum'}).reset_index()
ERR  = LT.copy(deep=True)

print("Finished loading light-table")
print("Aggregating light table...")

# LT: Sum the total charge collected in each sensor for a given voxel across all events and also over z in case of S2
# ERR: std of the total charge collected in each sensor for a given voxel across all events also over z in case of S2

# Main Light table
lt = LT.groupby(column_arr).agg({'N': 'sum', 'sum': 'sum', 'sum2': 'sum'}).reset_index() # Sum over z values
lt["mean"] = lt["sum"] / lt["N"]

# Error
err = ERR.groupby(column_arr).agg({'N': 'sum', 'sum': 'sum', 'sum2': 'sum'}).reset_index() # Sum over z values
err["mean"] = err["sum"] / err["N"]
err["std"] = 100*np.sqrt( (err.sum2/err.N - err["mean"]**2) )/err["mean"]

print(lt[lt["sum"]>0])
print(err[err["sum"]>0])

lt = lt.drop(columns=['sum', 'sum2', 'N'])
err = err.drop(columns=['sum', 'sum2', 'N', "mean"])

lt['mean'].fillna(0, inplace=True)
err['std'].fillna(0, inplace=True)

# Renaming
lt.rename(columns={'mean': 'charge'}, inplace=True)

print(lt[lt.charge > 0].head(10))
print(err[err["std"]>0].head(10))


# Now convert the format of the dataframe
LT  = pd.pivot_table(lt, values="charge", columns="sensor_id", index=index_arr)
ERR = pd.pivot_table(err, values="std", columns="sensor_id", index=index_arr)

# print(LT)

LT.columns = LT.columns.rename("")
ERR.columns = ERR.columns.rename("")

LT  = LT.reset_index()
ERR = ERR.reset_index()

# Rename the sensor columns to PMT number
for sid in sensorids:
    LT = LT.rename({sid: pmt + f"_{sid}"}, axis=1)
    ERR = ERR.rename({sid: pmt + f"_{sid}"}, axis=1)

# Add column for the total charge in the PMTs
LT[pmt + f"_total"] = LT.loc[:, LT.columns.difference(index_arr)].sum(axis=1)
ERR[pmt + f"_total"] = ERR.loc[:, ERR.columns.difference(index_arr)].sum(axis=1)

# Save the table to an output file
outfilename = f"NEXT100-MC_{signal_type}_LT.h5"


with tb.open_file(outfilename, 'w') as h5out:
    df_writer(h5out, LT, "LT", "LightTable")


with tb.open_file(outfilename, 'r+') as h5out:
    df_writer(h5out, config, "LT", "Config")


with tb.open_file(outfilename, 'r+') as h5out:
    df_writer(h5out, ERR, "LT", "Error")
