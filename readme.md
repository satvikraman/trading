# ICICI Direct
The ICICI Direct stock list containing ICICI Direct specific stock list was downloaded from this page [ICICI Direct Breeze API](https://api.icicidirect.com/breezeapi/documents/index.html?python#instruments) and more specifically [ICICI Direct Stock List](https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip). The file of interest from the archive is present in db\NSEScripMaster.txt

# NSE
The NSE stock list was downloaded from [All Companies based on Market Capitalisation](https://www.nseindia.com/regulations/listing-compliance/nse-market-capitalisation-all-companies). The original file downloaded on 31st Mar 2023 is present here db\MCAP31032023_0.xlsx

# PayTm
Further more datasets like the nse_security_master.csv file was downloaded from here https://developer.paytmmoney.com/docs/api/security-master/

# Scripts
## mapIciciToNseStock.py
This file is used to map the NSE and the ICICI Direct stock codes offline. This is an independent script which will generate the db\stkUniverse.csv file which will be subsequently used

# PyTest
To run all tests inside a particular directory run the following on the command line
`pytest --rootdir=<Path to the test directory>`
To run tests along with debugger in verbose mode, execute the following command
pytest -s -v --pdb <pytest_file> -k <pytest_function>
`pytest -s -v --pdb .\test\test_icicidirect.py -k test_formatInvRemarkCell`

Example: `pytest --rootdir=./test`

To run a test capturing the log output run the following on the command line 
`pytest -s --capture=no --log-cli-level=DEBUG <Path to the test script>`

Example: `pytest -s --capture=no --log-cli-level=DEBUG .\test\test_icicidirect.py`

# Requirements
To create the list of requirements enter the following command 
conda list -e > requirements.txt
To install the list of packages required enter the following command
conda install --file requirements.txt

# Working with JSON documents offline
Go to https://jsoneditoronline.org/
You may filter the json documents using lodash filter by writing something similar to what's shown below
  const res = _.filter(data._default, stock => stock.POS_HOLD_STATUS != 'CLOSE' && stock.VISIBLE == 'HIDDEN')
  return _.chain(res).value()