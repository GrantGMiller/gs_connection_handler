import extr_dsp_DMP64_v1_2_0_0 as GSM
from connection_handler import HandleConnection
from extronlib import event

device = GSM.EthernetClass('10.8.27.62', 23, Model='DMP 64')
HandleConnection(device, keepAliveQueryCommand='PartNumber')


@event(device, ['Connected', 'Disconnected'])
def DeviceConnectionEvent(interface, state):
    print('DeviceConnectionEvent(interface={}, state={})'.format(interface, state))


def ModuleCallback(c, v, q):
    print('ModuleCallback(c={}, v={}, q={})'.format(c, v, q))


device.SubscribeStatus('ConnectionStatus', None, ModuleCallback)
device.SubscribeStatus('OutputAttenuation', {'Output': '1'}, ModuleCallback)

