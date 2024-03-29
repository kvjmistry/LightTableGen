import os
import os.path
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
lt_dir = os.path.expandvars("./")
lt_filenames = glob.glob(os.path.join(lt_dir, "*.h5"))
lt_filenames = sorted(lt_filenames)
print(lt_filenames)

# Configure the detector database
detector_db = "new"
datapmt = load_db.DataPMT(detector_db, 0)
xpmt, ypmt = datapmt["X"].values, datapmt["Y"].values
sensorids  = datapmt["SensorID"].values

for i, filename in enumerate(lt_filenames, 0):

    # Load the MC Particle Tree to ger the intiial x, y, z positions sampled
    parts = pd.read_hdf(filename, 'MC/particles')
    parts = parts[['event_id', 'initial_x', 'initial_y', 'initial_z']]

    # Get the metadata from the files
    config = pd.read_hdf(filename, "MC/configuration")
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

    f_num_phot = {'nphotons':[nphotons], 'num_events':[num_events]}
    df = pd.DataFrame(data=f_num_phot)

    outfile_full = os.path.basename(filename)
    outfile = os.path.splitext(outfile_full)[0]
    outfilename = os.path.splitext(outfile)[0]
    outfilename = outfilename + "_slim.next.h5"
    print(outfilename)

    with tb.open_file(outfilename, 'w') as h5out:
        df_writer(h5out, pmt_response, "MC", "PMT_Response")

    with tb.open_file(outfilename, 'r+') as h5out:
        df_writer(h5out, df, "MC", "Config")


# How to read in:
# parts = pd.read_hdf(filename, 'MC/PMT_Response')
# parts = pd.read_hdf(filename, 'MC/Config')
