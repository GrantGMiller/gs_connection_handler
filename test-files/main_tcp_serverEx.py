from tcp_connection_handler import HandleConnection
from extronlib.interface import EthernetServerInterfaceEx
from extronlib import event

server = EthernetServerInterfaceEx(1024)


@event(server, 'ReceiveData')
def ServerRxEvent(client, data):
    print('ServerRxEvent(client={}, data={})'.format(client, data))
    print(client, data)


@event(server, ['Connected', 'Disconnected'])
def ServerConnectionEvent(client, state):
    print('ServerConnectionEvent(client={}, state={})'.format(client, state))


HandleConnection(server, serverTimeout=15)
