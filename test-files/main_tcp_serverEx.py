
from extronlib.interface import EthernetServerInterfaceEx
from extronlib import event
from connection_handler import HandleConnection

server = EthernetServerInterfaceEx(1024)
HandleConnection(server, serverTimeout=10)


@event(server, 'ReceiveData')
def ServerRxEvent(client, data):
    print('11 ServerRxEvent(client={}, data={})'.format(client, data))
    client.Send('echo: {}\r\n'.format(data))


@event(server, ['Connected', 'Disconnected'])
def ServerConnectionEvent(client, state):
    print('17 ServerConnectionEvent(client={}, state={})'.format(client, state))
    if state == 'Connected':
        client.Send('Welcome')


print('ready')