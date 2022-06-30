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


# Load in the files -- configure the path
lt_dir = os.path.expandvars("../files/S1_slim/")
lt_filenames = glob.glob(os.path.join(lt_dir, "*.h5"))
lt_filenames = sorted(lt_filenames)
print(lt_filenames)

# Configure the detector database
detector_db = "new"
datapmt = load_db.DataPMT(detector_db, 0)
xpmt, ypmt = datapmt["X"].values, datapmt["Y"].values
sensorids  = datapmt["SensorID"].values

plt.figure()
plt.scatter(xpmt, ypmt)
for x, y, sid  in zip(xpmt, ypmt, sensorids):
    plt.annotate(sid, (x, y))
plt.savefig("PMT_Positions.pdf")


# We first run over file 0 to populate the pandas dataframe
filename = lt_filenames[0] # First file in list
print("Starting with file: ",filename)

# Load the PMT Response and config dataframes
pmt_response = pd.read_hdf(filename, 'MC/PMT_Response')
config = pd.read_hdf(filename, 'MC/Config')

num_events = int(config["num_events"].iloc[0])
nphotons   = int(config["nphotons"].iloc[0])
print("Num Events:", num_events, "Num Photons:", nphotons)

# Set the Binning
xmin=-200
xmax=200
xbw=20

zmin=0
zmax=700
zbw=50

xbins = np.arange(xmin, xmax+xbw, xbw)
ybins = xbins
zbins = np.arange(zmin, zmax+zbw, zbw)

xbins_centre = np.arange(xmin+xbw/2, xmax+xbw/2, xbw)
ybins_centre = xbins_centre
zbins_centre = np.arange(zmin+zbw/2, zmax+zbw/2, zbw)

# Now bin the x, y, z positions into 3D voxels. We label the bins with the 
# midpoints
pmt_response['x'] = pd.cut(x=pmt_response['initial_x'], bins=xbins,labels=xbins_centre, include_lowest=True)
pmt_response['y'] = pd.cut(x=pmt_response['initial_y'], bins=ybins,labels=ybins_centre, include_lowest=True)
pmt_response['z'] = pd.cut(x=pmt_response['initial_z'], bins=zbins,labels=zbins_centre, include_lowest=True)

# remove the initial x,y,z since we are done with them
pmt_response = pmt_response.drop(columns=['initial_x', 'initial_y', 'initial_z'])

# Normalise the charge in each PMT by the total number of photons simulated
pmt_response['charge'] = pmt_response['charge']/nphotons

# Set the light table
LT = pmt_response
ERR = pmt_response

LT  = pd.DataFrame()
ERR = pd.DataFrame()

for i, filename in enumerate(lt_filenames, 1):
    sys.stdout.write(f"Processing file {i}/{len(lt_filenames)} \r")
    sys.stdout.flush()
    
    # Load the PMT Response and config dataframes
    pmt_response = pd.read_hdf(filename, 'MC/PMT_Response')
    config = pd.read_hdf(filename, 'MC/Config')

    num_events = int(config["num_events"].iloc[0])
    nphotons   = int(config["nphotons"].iloc[0])

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

# Sum the total charge collected in each sensor for a given voxel across all events
lt = LT.groupby(["sensor_id", "x", "y", "z"])["charge"].sum().to_frame().reset_index()

# STD of the total charge collected in each sensor for a given voxel across all events
err = LT.groupby(["sensor_id", "x", "y", "z"])["charge"].std().to_frame().reset_index()

# Now convert the format of the dataframe
LT  = pd.pivot_table(lt, values="charge", columns="sensor_id", index=["x", "y", "z"])
ERR = pd.pivot_table(err, values="charge", columns="sensor_id", index=["x", "y", "z"])

LT.columns = LT.columns.rename("")
ERR.columns = ERR.columns.rename("")

LT  = LT.reset_index()
ERR = ERR.reset_index()


pmt = "PmtR11410"
signal_type = "S1"

# Rename the sensor columns to PMT number
for sid in sensorids:
    LT = LT.rename({sid: pmt + f"_{sid}"}, axis=1)

# Add column for the total charge in the PMTs
LT[pmt + f"_total"] = LT.loc[:, LT.columns.difference(["x", "y", "z"])].sum(axis=1)

# Save the table to an output file
save = True
outfilename = f"NEW-MC_{signal_type}_LT.h5"

if save:
    with tb.open_file(outfilename, 'w') as h5out:
        df_writer(h5out, LT, "LT", "LightTable")

# create config and add to the file
config = { "detector"   : "new"
         , "ACTIVE_rad" : str(227)
         , "EL_GAP"     : str(6.0)
         , "table_type" : "energy"
         , "signal_type": signal_type
         , "sensor"     : pmt
         , "pitch_x"    : str(10)
         , "pitch_y"    : str(10)}

config = pd.DataFrame({"parameter": config.keys(), "value": config.values()})
if save:
    with tb.open_file(outfilename, 'r+') as h5out:
        df_writer(h5out, config, "LT", "Config")
