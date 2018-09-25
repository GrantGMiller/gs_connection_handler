'''
This file is meant to flood a server with connections in an attempt to break it.
Ideally, the server would be strong/smart enough to not break.
Good luck!
'''

from extronlib.interface import EthernetClientInterface

for i in range(300):
    print('i=', i)
    c = EthernetClientInterface('10.8.27.36', 9000)
    c.Connected = lambda interface, s, i=i: print('event', i, s, interface)
    c.Disconnected = lambda interface, s, i=i: print('event', i, s, interface)
    res = c.Connect(1)
    # print('res=', res)
    # c.Disconnect()
