
from extronlib.interface import EthernetServerInterface
from extronlib import event
from connection_handler import HandleConnection

server = EthernetServerInterface(1024)


@event(server, 'ReceiveData')
def ServerRxEvent(client, data):
    print('11 ServerRxEvent(client={}, data={})'.format(client, data))
    print(client, data)
    client.Send('echo', data)


@event(server, ['Connected', 'Disconnected'])
def ServerConnectionEvent(client, state):
    print('ServerConnectionEvent(client={}, state={})'.format(client, state))


HandleConnection(server, serverTimeout=15)
