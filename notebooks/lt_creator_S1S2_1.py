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

# Load in the input file
filename=sys.argv[1]

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

# Get the sum
lt_sum = pmt_response.groupby(["sensor_id", "x", "y", "z"])["charge"].sum().to_frame().reset_index()
lt_sum.rename(columns={'charge': 'sum'}, inplace=True)

# Get the sum of squares
pmt_response['sum2'] = np.square(pmt_response['charge'])
lt_sum_of_squares = pmt_response.groupby(["sensor_id", "x", "y", "z"])["sum2"].sum().to_frame().reset_index()

# Merge the results from the sub-calculations
LT = pd.merge(lt_count, lt_sum, on=["sensor_id", "x", "y","z"])
LT = pd.merge(LT, lt_sum_of_squares, on=["sensor_id", "x", "y","z"])
    
# Consolodate the duplicate rows
LT = LT.groupby(['sensor_id', 'x', 'y', 'z']).agg({'N': 'sum', 'sum': 'sum', 'sum2': 'sum'}).reset_index()

print("Finished loading light-table")
print("Aggregating light table...")


# Save the table to an output file
index=sys.argv[2]

with pd.HDFStore(f"NEXT100-MC_{signal_type}_LT_Step1_{index}.h5", mode='w', complevel=5, complib='zlib') as store:
    # Write each DataFrame to the file with a unique key
    store.put('LT/LightTable', LT, format='table')
    store.put('LT/Config',config, format='table')