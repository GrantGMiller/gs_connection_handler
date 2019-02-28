
from extronlib import event
from extronlib.interface import EthernetClientInterface
from connection_handler import HandleConnection
import time

device = EthernetClientInterface('192.168.137.112', 23)
HandleConnection(
    device,
    keepAliveQueryCommand='q',
    timedDisconnect=10,
    pollFreq=1
)


@event(device, ['Connected', 'Disconnected'])
def DeviceConnectionEvent(interface, state):
    print('12', time.time(), 'DeviceConnectionEvent(interface={}, state={})'.format(interface, state))


@event(device, 'ReceiveData')
def DeviceRxData(interface, data):
    print('17 Rx:', time.time(), data)
