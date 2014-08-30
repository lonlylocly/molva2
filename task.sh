#!/bin/bash -ex

echo "$(date) Start"

SCRIPTDIR=/home/lonlylocly/woape
RUNDIR=/home/lonlylocly/run
SIMMER_JAR=Simmer-1.0-SNAPSHOT-jar-with-dependencies.jar

do_profiles() {
    $SCRIPTDIR/prepare-profiles.py -o profiles.json  > prepare-profiles.log 2>&1 
    java -Xmx700m -jar $SCRIPTDIR/$SIMMER_JAR profiles.json sims.csv > simmer.log 2>&1 
    $SCRIPTDIR/post-profiles.py -i sims.csv  > post-profiles.log 2>&1 
}

for d in 1 0 ; do
    date=$(date "+%Y%m%d" -d "now - $d day")

    $SCRIPTDIR/pre-tomita.py -s $date -e $date 1>> pre-tomita.log 2>&1  
    date
    $SCRIPTDIR/run-tomita.py 1>> run-tomita.log 2>run-tomita.err  
    date
    $SCRIPTDIR/parsefacts.py 1>> parsefacts.log 2>&1  
    date
    $SCRIPTDIR/post-tomita.py -s $date -e $date 1>> post-tomita.log 2>&1 

done

date=$(date "+%Y%m%d" -d "now")

date
$SCRIPTDIR/current-post-cnt.py >> current-post-cnt.log 2>&1 

do_profiles

$SCRIPTDIR/trend.py  1>> trend.log 2>&1 
# TODO по ходу эта шняга не работает
echo "$(date) exclusion"
$SCRIPTDIR/exclusion.py  1>> exclusion.log 2>&1 

echo "$(date) build clusters"
$SCRIPTDIR/prepare-aligner.py >> prepare-aligner.log 2>&1
$SCRIPTDIR/build-clusters.py   -i 10 1>> clusters.log 2>&1 

date
$SCRIPTDIR/show-db-stats.py -s $date -e $date

echo "done"


