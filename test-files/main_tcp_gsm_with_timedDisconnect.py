import extr_dsp_DMP_128_Plus_Series_v1_4_3_0 as dmpModule
import extr_sm_SMD202_v1_2_7_0 as smdModule
from connection_handler import HandleConnection
from extronlib import event
from extronlib.system import Wait
import extronlib
import time

try:
    extronlib.ExportForGS(
        r'C:\Users\gmiller\Desktop\Grants GUIs\GS Modules\Universal Connection Handler\TCP Connection Handler\PyCharmExport')
except:
    pass

gsModule = smdModule

# dvModuleEthernet = gsModule.EthernetClass('10.8.27.68', 23, Protocol='TCP', Model='SMD 202')
dvModuleEthernet = gsModule.EthernetClass('192.168.137.112', 23, Protocol='TCP', Model='SMD 202')
dvModuleEthernet.devicePassword = 'extron'

# dvModuleEthernet.connectionCounter = 5

if gsModule == dmpModule:
    cmd = 'VirtualReturnMute'
    qual = {'Channel': 'A'}
elif gsModule == smdModule:
    cmd = 'AudioMute'
    qual = None


@event(dvModuleEthernet, ['Connected', 'Disconnected'])
def ModuleEthernetStatus(interface, state):
    print('29 @event', interface, state)
    if state == 'Connected':
        # btnModuleEthernetStatus.SetState(1)
        pass
    else:
        # btnModuleEthernetStatus.SetState(0)
        pass
    # btnModuleEthernetStatus.SetText(state)


def NewEthernetStatus(command, value, qualifier):
    print('Subscribe:', command, value, qualifier)


HandleConnection(
    dvModuleEthernet,
    keepAliveQueryCommand=cmd,
    keepAliveQueryQualifier=qual,
    pollFreq=3,
    timedDisconnect=10,
)

dvModuleEthernet.SubscribeStatus('ConnectionStatus', None, NewEthernetStatus)
dvModuleEthernet.SubscribeStatus(cmd, qual, NewEthernetStatus)

# spam the interface with .Send and .SendAndWait to see if we can trick it into disconnecting
@Wait(10)
def Loop():
    while True:
        print('63 spam')
        for i in range(50):
            if i % 2 == 0:
                dvModuleEthernet.Send('{}\r'.format(i))
            else:
                dvModuleEthernet.SendAndWait('{}\r'.format(i), 0.01)

        time.sleep(60)
