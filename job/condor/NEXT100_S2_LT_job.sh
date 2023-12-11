#!/bin/bash

echo "Starting Job" 

JOBID=$1
echo "The JOBID number is: ${JOBID}" 

JOBNAME=$2
echo "The JOBNAME number is: ${JOBNAME}" 

echo "JOBID $1 running on `whoami`@`hostname`"
start=`date +%s`

# Setup nexus
echo "Setting Up NEXUS" 
source /software/nexus/setup_nexus.sh

# Set the configurable variables
N_PHOTONS=1000000
N_EVENTS=1
CONFIG=${JOBNAME}.config.mac
INIT=${JOBNAME}.init.mac

echo "N_PHOTONS: ${N_PHOTONS}, N_EVENTS: ${N_EVENTS}"

SEED=$((${N_EVENTS}*${JOBID} + ${N_EVENTS}))
echo "The seed number is: ${SEED}" 

# Change the config in the files
sed -i "s#.*output_file.*#/nexus/persistency/output_file NEW_S2_LT_${JOBID}.next#" ${CONFIG}
sed -i "s#.*nphotons.*#/Generator/ScintGenerator/nphotons ${N_PHOTONS}#" ${CONFIG}
sed -i "s#.*random_seed.*#/nexus/random_seed ${SEED}#" ${CONFIG}
sed -i "s#.*start_id.*#/nexus/persistency/start_id ${SEED}#" ${CONFIG}
sed -i "s#.*useDielectricGrid.*#/Geometry/Next100/useDielectricGrid false#" ${CONFIG}

# Print out the config and init files
cat ${INIT}
cat ${CONFIG}

# NEXUS
echo "Running NEXUS" 
nexus -n $N_EVENTS ${INIT}

echo "FINISHED....EXITING" 

end=`date +%s`
let deltatime=end-start
let hours=deltatime/3600
let minutes=(deltatime/60)%60
let seconds=deltatime%60
printf "Time spent: %d:%02d:%02d\n" $hours $minutes $seconds 