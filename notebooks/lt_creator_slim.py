import os
import re
import sys
import glob
import numpy  as np
import pandas as pd
import tables as tb
import matplotlib.pyplot as plt

from invisible_cities.database  import load_db
from invisible_cities.io.dst_io import load_dst
from invisible_cities.io.dst_io import df_writer

# Takes in the slim file format


# Configure the script here
signal_type = "S2" # S1/S2
detector_db = "next100"
pmt = "PmtR11410"
Active_r = 1000 # active radius in mm
EL_GAP = 10.0 # EL gap in mm
SiPM_Pitch = 15
save=True
save_Err=True


# Set the Binning

# S1
if signal_type == "S1":
    # Min x val, max x val, x bin w (y are set equal to this)
    xmin=-500; xmax=500; xbw=20

    # Min z val, max z val, z bin w
    zmin=0; zmax=510; zbw=20
# S2
else:
    # Min x val, max x val, x bin w (y are set equal to this)
    xmin=-500; xmax=500; xbw=20

    # Min z val, max z val, z bin w (in case of S2, we just want one bin in EL)
    zmin=-12; zmax=2; zbw=1


# create config which will be saved to the file
config = { "parameter" : ["detector",  "ACTIVE_rad", "EL_GAP"   , "table_type","signal_type","sensor","pitch_x"       ,"pitch_y", "nexus"], 
                "value": [detector_db, str(Active_r),str(EL_GAP), "energy"     ,signal_type , pmt     ,str(SiPM_Pitch), str(SiPM_Pitch), "v7_08_00"]}

config = pd.DataFrame.from_dict(config)

# Load in the files -- configure the path

if signal_type == "S1":
    lt_dir = os.path.expandvars("../files/NEXT100_S1_LT/")
else: 
    lt_dir = os.path.expandvars("../files/next100/NEXT100_S2_LT/")

lt_filenames = glob.glob(os.path.join(lt_dir, "*.h5"))
lt_filenames = sorted(lt_filenames)
print(lt_filenames)

# Configure the detector database
datapmt = load_db.DataPMT(detector_db, 0)
xpmt, ypmt = datapmt["X"].values, datapmt["Y"].values
sensorids  = datapmt["SensorID"].values

# Create the bins
xbins = np.arange(xmin, xmax+xbw, xbw)
ybins = xbins
zbins = np.arange(zmin, zmax+zbw, zbw)

xbins_centre = np.arange(xmin+xbw/2, xmax+xbw/2, xbw)
ybins_centre = xbins_centre
zbins_centre = np.arange(zmin+zbw/2, zmax+zbw/2, zbw)


LT  = pd.DataFrame()
ERR = pd.DataFrame()

for i, filename in enumerate(lt_filenames, 0):
    sys.stdout.write(f"Processing file {i}/{len(lt_filenames)} \r")
    sys.stdout.flush()

    # Load the MC Particle Tree to ger the intiial x, y, z positions sampled
    parts = pd.read_hdf(filename, 'MC/particles')
    parts = parts[['event_id', 'initial_x', 'initial_y', 'initial_z']]

    # Get the metadata from the files
    configuration = pd.read_hdf(filename, "MC/configuration").set_index("param_key")
    num_events = int(configuration.loc["num_events"][0])
    nphotons   = int(configuration.loc["/Generator/ScintGenerator/nphotons"][0])

    # Get the sensor response information
    sns_response  = pd.read_hdf(filename, "MC/sns_response")
    pmt_response  = sns_response[np.isin(sns_response["sensor_id"].values, datapmt["SensorID"].values)]

    # Sum total charge over all time bins
    pmt_response = pmt_response.groupby(["sensor_id", "event_id"])["charge"].sum().to_frame().reset_index()

    # Merge the MC Particle and Sensor dataframes to add the x, y, z positions
    pmt_response = pmt_response.merge(parts, on="event_id", how = 'inner')
    
    # Now bin the x, y, z positions
    pmt_response['x'] = pd.cut(x=pmt_response['initial_x'], bins=xbins,labels=xbins_centre, include_lowest=True)
    pmt_response['y'] = pd.cut(x=pmt_response['initial_y'], bins=ybins,labels=ybins_centre, include_lowest=True)
    pmt_response['z'] = pd.cut(x=pmt_response['initial_z'], bins=zbins,labels=zbins_centre, include_lowest=True)

    # remove the initial x,y,z since we are done with them
    pmt_response = pmt_response.drop(columns=['initial_x', 'initial_y', 'initial_z'])

    # Normalise the charge in each PMT by the total number of photons simulated
    pmt_response['charge'] = pmt_response['charge']/nphotons


    # Get the count of entries
    lt_count = pmt_response.groupby(["sensor_id", "x", "y", "z"])["charge"].count().to_frame().reset_index()
    lt_count.rename(columns={'charge': 'N'}, inplace=True)

    # Use sum instead of mean
    lt_sum = pmt_response.groupby(["sensor_id", "x", "y", "z"])["charge"].sum().to_frame().reset_index()
    lt_sum.rename(columns={'charge': 'sum'}, inplace=True)

    # Get the sum of squares
    pmt_response['charge_squared'] = np.square(LT['charge'])
    lt_sum_of_squares = pmt_response.groupby(["sensor_id", "x", "y", "z"])["charge_squared"].sum().to_frame().reset_index()
    lt_sum_of_squares.rename(columns={'charge_squared': 'sum2'}, inplace=True)

    # Merge the results
    result = pd.merge(lt_count, lt_sum, on=["sensor_id", "x", "y","z"])
    result = pd.merge(result, lt_sum_of_squares, on=["sensor_id", "x", "y","z"])

    # Add the dataframe
    LT  = pd.concat([LT , result])

print("Finished loading light-table")
print("Aggregating light table...")

# # LT: Sum the total charge collected in each sensor for a given voxel across all events and also over z in case of S2
# # ERR: std of the total charge collected in each sensor for a given voxel across all events also over z in case of S2
# if signal_type == "S2":
#     lt = LT.groupby(["sensor_id", "x", "y"])["charge"].mean().to_frame().reset_index()
#     err = LT.groupby(["sensor_id", "x", "y"])["charge"].std().to_frame().reset_index() 
# else: 
    
#     lt = LT.groupby(["sensor_id", "x", "y", "z"])["charge"].mean().to_frame().reset_index()
#     err = LT.groupby(["sensor_id", "x", "y", "z"])["charge"].std().to_frame().reset_index() 
#     # err = LT.groupby(["sensor_id", "x", "y", "z"])["charge"].nunique().to_frame().reset_index()

# # Calculate error values
# err['charge'] = 100*err['charge']/lt['charge']

# # Now convert the format of the dataframe

# if signal_type == "S2":
#     LT  = pd.pivot_table(lt, values="charge", columns="sensor_id", index=["x", "y"])
#     ERR = pd.pivot_table(err, values="charge", columns="sensor_id", index=["x", "y"])
# else: 
#     LT  = pd.pivot_table(lt, values="charge", columns="sensor_id", index=["x", "y", "z"])
#     ERR = pd.pivot_table(err, values="charge", columns="sensor_id", index=["x", "y", "z"])


# LT.columns = LT.columns.rename("")
# ERR.columns = ERR.columns.rename("")

# LT  = LT.reset_index()
# ERR = ERR.reset_index()

# # Rename the sensor columns to PMT number
# for sid in sensorids:
#     LT = LT.rename({sid: pmt + f"_{sid}"}, axis=1)
#     ERR = ERR.rename({sid: pmt + f"_{sid}"}, axis=1)

# # Add column for the total charge in the PMTs
# if signal_type == "S2":
#     LT[pmt + f"_total"] = LT.loc[:, LT.columns.difference(["x", "y"])].sum(axis=1)
#     ERR[pmt + f"_total"] = ERR.loc[:, ERR.columns.difference(["x", "y"])].sum(axis=1)
# else:
#     LT[pmt + f"_total"] = LT.loc[:, LT.columns.difference(["x", "y", "z"])].sum(axis=1)
#     ERR[pmt + f"_total"] = ERR.loc[:, ERR.columns.difference(["x", "y", "z"])].sum(axis=1)

# # Save the table to an output file
# outfilename = f"../LT/NEXT100-MC_{signal_type}_LT_FakeGrid.h5"

# if save:
#     with tb.open_file(outfilename, 'w') as h5out:
#         df_writer(h5out, LT, "LT", "LightTable")

# if save:
#     with tb.open_file(outfilename, 'r+') as h5out:
#         df_writer(h5out, config, "LT", "Config")

# if save_Err:
#     with tb.open_file(outfilename, 'r+') as h5out:
#         df_writer(h5out, ERR, "LT", "Error")
