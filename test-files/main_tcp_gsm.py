import extr_dsp_DMP_128_Plus_Series_v1_4_3_0 as gsModule
# import extr_sm_SMD202_v1_2_7_0 as gsModule
from connection_handler import HandleConnection
from extronlib import event
import extronlib

try:
    extronlib.ExportForGS(
        r'C:\Users\gmiller\Desktop\Grants GUIs\GS Modules\Universal Connection Handler\TCP Connection Handler\PyCharmExport')
except:
    pass

dvModuleEthernet = gsModule.EthernetClass('10.8.27.130', 23, Protocol='TCP', Model='SMD 202')
dvModuleEthernet.devicePassword = 'extron'
cmd = 'VirtualReturnMute'
qual = {'Channel': 'A'}


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
