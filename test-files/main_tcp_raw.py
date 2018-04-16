from tcp_connection_handler import HandleConnection
from extronlib import event
from extronlib.interface import EthernetClientInterface

device = EthernetClientInterface('10.8.27.62', 23)
HandleConnection(device, keepAliveQueryCommand='q')


@event(device, ['Connected', 'Disconnected'])
def DeviceConnectionEvent(interface, state):
    print('DeviceConnectionEvent(interface={}, state={})'.format(interface, state))

@event(device, 'ReceiveData')
def DeviceRxData(interface, data):
    print('Rx:', data)