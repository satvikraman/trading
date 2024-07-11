#!/bin/bash

# Change directory to where the Python script is located
cd /home/arvind/trading/trading
# Activate the Anaconda environment
source ../trd_chrome/bin/activate

# Function to get current hour and minute
get_hour() {
    date "+%H"
}

get_minute() {
    date "+%M"
}

# Main loop
while true; do
    python src/paytm/appPaytm.py
    sleep 5

    HOUR=$(get_hour)
    MIN=$(get_minute)

    if [ $HOUR -lt 15 ]; then
        echo "Restarting appPayTm at $HOUR:$MIN"
    elif [ $HOUR -eq 15 ] && [ $MIN -le 30 ]; then
        echo "Restarting appPayTm at $HOUR:$MIN"
    else
        break
    fi
done
