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


# Configure the script here
signal_type = "S2"
detector_db = "new"
pmt = "PmtR11410" # name of the PMT
Active_r = 208.0 # active radius in mm
EL_GAP = 6.0 # EL gap in mm
SiPM_Pitch = 10 # in mm
save = True
save_Err = False

# Set the Binning
if signal_type == "S1":
    # Min x val, max x val, x bin w (y are set equal to this)
    xmin=-210; xmax=210; xbw=20

    # Min z val, max z val, z bin w
    zmin=0; zmax=510; zbw=25
else:
    # Min x val, max x val, x bin w (y are set equal to this)
    xmin=-210; xmax=210; xbw=5

    # Min z val, max z val, z bin w (in case of S2, we just want one bin in EL)
    zmin=-10; zmax=0; zbw=10

# create config which will be saved to the file
config = { "parameter" : ["detector","ACTIVE_rad","EL_GAP"    , "table_type","signal_type","sensor","pitch_x"       ,"pitch_y"], 
                "value": ["new"     ,str(Active_r),str(EL_GAP), "energy"     ,signal_type , pmt     ,str(SiPM_Pitch), str(SiPM_Pitch)]}

config = pd.DataFrame.from_dict(config)

# Load in the files -- configure the path
if signal_type == "S1":
    lt_dir = os.path.expandvars("../files/S1/")
else: 
    lt_dir = os.path.expandvars("../files/S2/")


# lt_dir = os.path.expandvars("$SCRATCH/guenette_lab/Users/$USER/NEW_S1_LT/")
lt_filenames = glob.glob(os.path.join(lt_dir, "*/*.h5"))

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

# Loop over the input files
for i, filename in enumerate(lt_filenames, 0):
    sys.stdout.write(f"Processing file {i}/{len(lt_filenames)} \r")
    sys.stdout.flush()
    
    # Load in the configurations
    configuration = pd.read_hdf(filename, "MC/configuration").set_index("param_key")
    num_events = int(configuration.loc["num_events"][0])
    nphotons   = int(configuration.loc["/Generator/ScintGenerator/nphotons"][0])

    # Load in the sensor data
    sns_response  = pd.read_hdf(filename, "MC/sns_response")
    pmt_response  = sns_response[np.isin(sns_response["sensor_id"].values, datapmt["SensorID"].values)]
    
    # Get the total charge over all time bins by summing
    pmt_response = pmt_response.groupby(["sensor_id", "event_id"])["charge"].sum().to_frame().reset_index()

    # Load in the MC Particles
    parts = pd.read_hdf(filename, 'MC/particles')
    parts = parts[['event_id', 'initial_x', 'initial_y', 'initial_z']]

    # Merge the dataframes
    pmt_response = pmt_response.merge(parts, on="event_id", how = 'inner')

    # Now bin the x, y, z positions
    pmt_response['x'] = pd.cut(x=pmt_response['initial_x'], bins=xbins,labels=xbins_centre, include_lowest=True)
    pmt_response['y'] = pd.cut(x=pmt_response['initial_y'], bins=ybins,labels=ybins_centre, include_lowest=True)
    pmt_response['z'] = pd.cut(x=pmt_response['initial_z'], bins=zbins,labels=zbins_centre, include_lowest=True)

    # remove the initial x,y,z since we are done with them
    pmt_response = pmt_response.drop(columns=['initial_x', 'initial_y', 'initial_z'])

    # Normalise the charge in each PMT by the total number of photons simulated
    pmt_response['charge'] = pmt_response['charge']/nphotons
    
    # Add the dataframe
    LT  = pd.concat([LT , pmt_response])
    ERR = pd.concat([ERR, pmt_response])

# Get the mean charge collected in each sensor for a given voxel across all events
lt = LT.groupby(["sensor_id", "x", "y", "z"])["charge"].mean().to_frame().reset_index()

# STD of the total charge collected in each sensor for a given voxel across all events
err = LT.groupby(["sensor_id", "x", "y", "z"])["charge"].std().to_frame().reset_index()

# Calculate error values
err['charge'] = 100*err['charge']/lt['charge']

# Now convert the format of the dataframe
LT  = pd.pivot_table(lt, values="charge", columns="sensor_id", index=["x", "y", "z"])
ERR = pd.pivot_table(err, values="charge", columns="sensor_id", index=["x", "y", "z"])

LT.columns = LT.columns.rename("")
ERR.columns = ERR.columns.rename("")

LT  = LT.reset_index()
ERR = ERR.reset_index()


# Rename the sensor columns to PMT number
for sid in sensorids:
    LT = LT.rename({sid: pmt + f"_{sid}"}, axis=1)
    ERR = ERR.rename({sid: pmt + f"_{sid}"}, axis=1)

if signal_type == "S2":
    LT = LT.drop("z", axis=1)

# Add column for the total charge in the PMTs
LT[pmt + f"_total"] = LT.loc[:, LT.columns.difference(["x", "y", "z"])].sum(axis=1)
ERR[pmt + f"_total"] = ERR.loc[:, ERR.columns.difference(["x", "y", "z"])].sum(axis=1)

# Save the table to an output file
outfilename = f"NEW-MC_{signal_type}_LT.h5"

if save:
    with tb.open_file(outfilename, 'w') as h5out:
        df_writer(h5out, LT, "LT", "LightTable")

if save:
    with tb.open_file(outfilename, 'r+') as h5out:
        df_writer(h5out, config, "LT", "Config")

if save_Err:
    with tb.open_file(outfilename, 'r+') as h5out:
        df_writer(h5out, ERR, "LT", "Error")
