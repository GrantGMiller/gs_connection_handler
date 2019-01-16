'''
This file is meant to flood a server with connections in an attempt to break it.
Ideally, the server would be strong/smart enough to not break.
Good luck!
'''

from extronlib.interface import EthernetClientInterface

for i in range(400):
    print('i=', i)
    c = EthernetClientInterface('10.8.27.21', 3888)
    c.Connected = lambda interface, s, i=i: print('event', i, s, interface)
    c.Disconnected = lambda interface, s, i=i: print('event', i, s, interface)
    res = c.Connect(1)
    if res in ['Connected']:
        c.Send('Sent from {}'.format(i))

    # c.Disconnect() # un/comment this to test conneting then disconnecting quickly
