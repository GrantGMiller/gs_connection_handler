import extr_dsp_DMP64_v1_2_0_0 as gsModule
from connection_handler import HandleConnection
from extronlib import event
import extronlib

try:
    extronlib.ExportForGS(
        r'C:\Users\gmiller\Desktop\Grants GUIs\GS Modules\Universal Connection Handler\TCP Connection Handler\PyCharmExport')
except:
    pass

dvModuleEthernet = gsModule.EthernetClass('10.8.27.62', 23, Protocol='TCP')
dvModuleEthernet.devicePassword = 'extron'
cmd = 'OutputAttenuation'
qual = {'Output': '1'}


@event(dvModuleEthernet, ['Connected', 'Disconnected'])
def ModuleEthernetStatus(interface, state):
    print('@event', interface, state)
    if state == 'Connected':
        # btnModuleEthernetStatus.SetState(1)
        pass
    else:
        # btnModuleEthernetStatus.SetState(0)
        pass
    # btnModuleEthernetStatus.SetText(state)


def NewEthernetStatus(command, value, qualifier):
    print('Subscribe:', command, value, qualifier)


HandleConnection(dvModuleEthernet, keepAliveQueryCommand=cmd, keepAliveQueryQualifier=qual, pollFreq=1)

dvModuleEthernet.SubscribeStatus('ConnectionStatus', None, NewEthernetStatus)
dvModuleEthernet.SubscribeStatus(cmd, qual, NewEthernetStatus)
