import sys
sys.path.append('./src')
import pytest
import mapIciciToNseStock

@pytest.fixture
def setup():
    mapper = mapIciciToNseStock.mapIciciToNseStock('./application.ini')
    return(mapper)

def test_mapIciciToNseStock(setup):
    mapper = setup
    mapDict = mapper.mapIcici2Nse('PVRLIM', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'PVRINOX'
    mapDict = mapper.mapIcici2Nse('ASIPAI', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'ASIANPAINT'
    mapDict = mapper.mapIcici2Nse('KOTMAH', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'KOTAKBANK'
    mapDict = mapper.mapIcici2Nse('HERHON', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'HEROMOTOCO'
    mapDict = mapper.mapIcici2Nse('JINSP', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'JINDALSTEL'
    mapDict = mapper.mapIcici2Nse('LARTOU', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'LT'
    mapDict = mapper.mapIcici2Nse('DIVLAB', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'DIVISLAB'
    mapDict = mapper.mapIcici2Nse('EIHLIM', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'EIHOTEL'
    mapDict = mapper.mapIcici2Nse('KPITEC', 'EQ')
    assert mapDict['NSE_SYMBOL'] == 'BSOFT'
