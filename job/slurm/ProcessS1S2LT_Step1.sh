#!/bin/bash
#SBATCH -J LT_Step1 # A single job name for the array
#SBATCH --nodes=1
#SBATCH --mem 4000 # Memory request (6Gb)
#SBATCH -t 0-1:00 # Maximum execution time (D-HH:MM)
#SBATCH -o LT_Step1_%A_%a.out # Standard output
#SBATCH -e LT_Step1_%A_%a.err # Standard error

start=`date +%s`


HOME=/home/argon/Projects/Krishan/LightTableGen/

# Setup nexus and run
echo "Setting up IC"
source /home/argon/Projects/Krishan/IC/setup_IC.sh

mkdir -p /media/argon/HDD_8tb/Krishan/LightTables/NEXT100_S2_LT_Step1/S2/
cd       /media/argon/HDD_8tb/Krishan/LightTables/NEXT100_S2_LT_Step1/S2/

# Get the nth file from the list
file=$(sed -n "${SLURM_ARRAY_TASK_ID}{p;q;}"  /media/argon/HDD_8tb/Krishan/LightTables/filelist_s2.txt)

# Launch nexus
python3 $HOME/notebooks/lt_creator_S1S2_1.py "${file}"

echo "FINISHED....EXITING"

end=`date +%s`
let deltatime=end-start
let hours=deltatime/3600
let minutes=(deltatime/60)%60
let seconds=deltatime%60
printf "Time spent: %d:%02d:%02d\n" $hours $minutes $seconds 