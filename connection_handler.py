import extronlib
from extronlib.system import Wait, File, ProgramLog

import time

from collections import defaultdict

__version__ = '0.0.5'
'''
VERSION HISTORY ***************

v0.0.5 - 2018-05-02
Bug Fixed. SendAndWait can throw TypeError "missing positional arg "msg"". Added handling and ProgramLog for this.

v0.0.4 - 2018-04-27
Bug Fixed. GSM not re-connecting. When GSM is logically disconnected, connection_callback would destroy reconnectWait before it would fire

v0.0.3 - 2018-04-24
When GSM is gracefully disconnected from server-side, module.OnDisconnected() was not called. This has been fixed.

v0.0.1 - 2018-04-17
ServerEx - fix requirement for order of @event/HandleConnection
Change class name to ConnectionHandler
change module name to connection_handler
Fixed bug where disconnecting multiple undead clients had the wrong timing

v0.0.0 - started with UCH v1.0.7
Strip down to only include TCP connections (Server/Client/SSH/GSM)
'''

debug = False
if not debug:
    print = lambda *a, **k: None
    pass
else:
    oldPrint = print


    def NewPrint(*a, **k):
        oldPrint(time.time(), *a, **k)
        time.sleep(0.002)


    print = NewPrint


def HandleConnection(interface, *args, **kwargs):
    if ConnectionHandler.GetDefaultCH() is None:
        filename = kwargs.pop('log_filename', 'connection_handler.log')
        ConnectionHandler.SetDefaultCH(ConnectionHandler(filename=filename))
    ConnectionHandler.GetDefaultCH().maintain(interface, *args, **kwargs)

    return ConnectionHandler.GetDefaultCH()


def IsConnected(interface):
    if ConnectionHandler.GetDefaultCH() is None:
        return False
    else:
        status = ConnectionHandler.GetDefaultCH().get_connection_status(interface)
        if status == 'Connected':
            return True
        else:
            return False


def GetInterfaces():
    # Returns a list of all the interfaces being handled by the default handler
    if ConnectionHandler.GetDefaultCH() is not None:
        return ConnectionHandler.GetDefaultCH().GetAllInterfaces()
    else:
        return []


class ConnectionHandler:
    '''
    This class handles TCP connections. Including Server/Client/GSM's/SSH
    '''
    _defaultCH = None

    @classmethod
    def GetDefaultCH(cls):
        return cls._defaultCH

    @classmethod
    def SetDefaultCH(cls, obj):
        cls._defaultCH = obj

    def GetAllInterfaces(self):
        return self._interfaces.copy()

    def __init__(self, filename='connection_handler.log'):
        '''
        :param filename: str() name of file to write connection status to
        '''
        self._interfaces = set()
        self._connection_status = {
            # interface: 'Connected',
        }
        self._connected_callback = None  # callable
        self._disconnected_callback = None

        self._timers = {  # Used for polling and for checking server timeouts
            # interface: Timer_obj,
        }
        self._connectionRetryFreqs = {
            # interface: float() #number of seconds between retrys
        }
        self._connection_timeouts = {
            # interface: float() #number of seconds to timeout trying to connect
        }
        self._send_counters = {
            # interface: int() #number of times data has been sent without receiving a response
        }
        self._disconnectLimits = {
            # interface: int() #number of times to miss a response before triggering disconnected status
        }
        self._rx_handlers = {
            # interface: function #function must take 2 params, "interface" object and "data" bytestring
        }
        self._connected_handlers = {
            # interface: function
        }
        self._disconnected_handlers = {
            # interface: function
        }
        self._user_connected_handlers = {
            # interface: function
        }
        self._user_disconnected_handlers = {
            # interface: function
        }
        self._logPhysicalConnection = defaultdict(bool)
        # interface: bool

        self._logLogicalConnection = defaultdict(bool)
        # interface: bool

        self._send_methods = {
            # interface: function
        }
        self._send_and_wait_methods = {
            # interface: function
        }

        self._server_listen_status = {
            # interface: 'Listening' or 'Not Listening' or other
        }

        self._server_client_rx_timestamps = {
            # EthernetServerInterfaceEx1: {ClientObject1A: timestamp1,
            # ClientObject1B: timestamp2,
            # },
            # EthernetServerInterfaceEx2: {ClientObject2A: timestamp3,
            # ClientObject2B: timestamp4,
            # },
        }

        self._keepAliveQueryCommands = {
            # interface: 'string',
        }

        self._keepAliveQueryQualifiers = {
            # interface: dict(),
        }
        self._pollFreqs = {
            # interface: float(),
        }

        self._connectWaits = {
            # interface: Wait(float(), interface.Connect)# we need to keep track of these so we dont create a bunch of waits that are waiting to connect. We only need one
        }

        self._filename = filename
        if not File.Exists(self._filename):
            with File(self._filename, mode='wt') as file:
                file.write('***\n\n\nProcessor Restarted at {}\r\n\r\n'.format(time.asctime()))
        else:
            # The file already exists, but lets add a message to know the processor restarted
            with File(self._filename, mode='at') as file:
                file.write('***\n\n\nProcessor Restarted at {}\r\n\r\n'.format(time.asctime()))

    def maintain(self,
                 interface,
                 keepAliveQueryCommand=None,
                 # Can be a module command like 'Power' when using a GSM, or a raw string like 'q'
                 keepAliveQueryQualifier=None,  # For extron modules. Ex: {'ID': '1'}
                 pollFreq=5,  # how many seconds between polls
                 disconnectLimit=5,  # how many missed queries before a 'Disconnected' event is triggered
                 serverTimeout=5 * 60,
                 # After this many seconds, a client who has not sent any data to the server will be disconnected.
                 connectionRetryFreq=5,  # how many seconds after a Disconnect event to try to do Connect
                 logPhysicalConnection=True,  # Log physical connection changes to the connection.log file
                 logLogicalConnection=True,  # Log logical connection changes to the connection.log file
                 ):
        '''
        This method will maintain the connection to the interface.
        :param interface: extronlib.interface or extron GS module with .SubscribeStatus('ConnectionStatus')
        :param keepAliveQueryCommand: string like 'q' for extron FW query, or string like 'Power' will send interface.Update('Power')
        :param keepAliveQueryQualifier: dict() For extron modules. Ex: {'ID': '1'}
        :param pollFreq: float - how many seconds between polls
        :param disconnectLimit: int - how many missed queries before a 'Disconnected' event is triggered
        :param serverTimeout: int - After this many seconds, a client who has not sent any data to the server will be disconnected.
        :param connectionRetryFreq: int - how many seconds after a Disconnect event to try to do Connect
        :return:
        '''
        print(
            'maintain()\ninterface={}\nkeepAliveQueryCommand="{}"\nkeepAliveQueryQualifier={}\npollFreq={}\ndisconnectLimit={}\nserverTimeout={}\nconnectionRetryFreq={}\nlog_connection={}\nlogLogicalConnection={}\n\n'.format(
                interface,
                keepAliveQueryCommand,
                keepAliveQueryQualifier,
                pollFreq,
                disconnectLimit,
                serverTimeout,
                connectionRetryFreq,
                logPhysicalConnection,
                logLogicalConnection,
            ))
        self._logPhysicalConnection[interface] = logPhysicalConnection
        self._logLogicalConnection[interface] = logLogicalConnection
        self._connection_timeouts[interface] = serverTimeout
        self._connectionRetryFreqs[interface] = connectionRetryFreq
        self._disconnectLimits[interface] = disconnectLimit
        self._keepAliveQueryCommands[interface] = keepAliveQueryCommand
        self._keepAliveQueryQualifiers[interface] = keepAliveQueryQualifier
        self._pollFreqs[interface] = pollFreq
        self._interfaces.add(interface)

        if isinstance(interface, extronlib.interface.EthernetClientInterface):
            self._maintain_serial_or_ethernetclient(interface)

        elif isinstance(interface, extronlib.interface.SerialInterface):
            self._maintain_serial_or_ethernetclient(interface)

        elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            if interface.Protocol == 'TCP':
                self._maintain_serverEx_TCP(interface)
            else:
                raise Exception(
                    'This ConnectionHandler class does not support EthernetServerInterfaceEx with Protocol="UDP".\r\nConsider using EthernetServerInterface with Protocol="UDP" (non-EX) without this handler.')

        elif isinstance(interface, extronlib.interface.EthernetServerInterface):

            if interface.Protocol in {'TCP', 'SSH'}:
                raise Exception(
                    'This ConnectionHandler class does not support EthernetServerInterface with Protocol="TCP".\r\nConsider using EthernetServerInterfaceEx with Protocol="TCP".')

            elif interface.Protocol == 'UDP':
                raise Exception(
                    'This ConnectionHandler class does not support EthernetServerInterface with Protocol="UDP".\r\nConsider using EthernetServerInterfaceEx.')

    def _maintain_serverEx_TCP(self, parent):
        print('_maintain_serverEx_TCP parent.Connected=', parent.Connected)
        print('_maintain_serverEx_TCP parent.Disconnected=', parent.Disconnected)

        # save old handlers
        if parent not in self._user_connected_handlers:
            self._user_connected_handlers[parent] = parent.Connected

        if parent not in self._user_disconnected_handlers:
            self._user_disconnected_handlers[parent] = parent.Disconnected

        print('_maintain_serverEx_TCP self._user_connected_handlers=', self._user_connected_handlers)
        print('_maintain_serverEx_TCP self._user_disconnected_handlers=', self._user_disconnected_handlers)

        if self._user_connected_handlers[parent] is None or \
                self._user_connected_handlers[parent].__module__ is not __name__:
            parent.Connected = self._get_serverEx_connection_callback(parent)

        if self._user_disconnected_handlers[parent] is None or \
                self._user_disconnected_handlers[parent].__module__ is not __name__:
            parent.Disconnected = self._get_serverEx_connection_callback(parent)

        if parent in self._timers:
            print('Stopping old timer')
            self._timers[parent].Stop()

        print('Creating new undead Timer')
        new_timer = Timer(
            self._connection_timeouts[parent],
            lambda p=parent: self._disconnect_undead_clients(p)
        )
        new_timer.Stop()

        self._timers[parent] = new_timer

        self._server_start_listening(parent)

        '''If HandleConnection(server) is called before 
            @event(s, ['Connected', 'Disconnected]) 
            or before @event(s, 'ReceiveData')
            Then the CH event are overridden by the @events
            
            We need to check periodically to make sure the handlers are from this CH
            and not from another module.
        '''
        if None in {self._user_connected_handlers[parent], self._user_disconnected_handlers[parent]}:
            @Wait(1)
            def RecheckUserConnectionHandlers(p=parent):
                print('RecheckUserConnectionHandlers')
                self._maintain_serverEx_TCP(p)

    def _server_start_listening(self, parent):
        '''
        This method will try to StartListen on the server. If it fails, it will retry every X seconds
        :param parent: extronlib.interface.EthernetServerInterfaceEx or EthernetServerInterface
        :return:
        '''
        if parent not in self._server_listen_status:
            self._server_listen_status[parent] = 'Unknown'

        if self._server_listen_status[parent] is not 'Listening':
            try:
                result = parent.StartListen()
            except Exception as e:
                result = 'Failed to StartListen: {}'.format(e)
                print('StartListen on port {} failed\n{}'.format(parent.IPPort, e))

            print('StartListen result=', result)

            self._server_listen_status[parent] = result

        if self._server_listen_status[parent] is not 'Listening':
            # We tried to start listen but it failed.
            # Try again in X seconds
            def retry_start_listen():
                self._server_start_listening(parent)

            Wait(self._connectionRetryFreqs[parent], retry_start_listen)

        elif self._server_listen_status[parent] is 'Listening':
            # We have successfully started the server listening
            pass

    def _maintain_serial_or_ethernetclient(self, interface):
        print('_maintain_serial_or_ethernetclient(interface={})'.format(interface))
        # Add polling
        if self._keepAliveQueryCommands[interface] is not None:
            # For example
            if hasattr(interface, 'Update{}'.format(self._keepAliveQueryCommands[interface])):

                # Delete any old polling engine timers
                if interface in self._timers:
                    self._timers[interface].Stop()
                    self._timers.pop(interface)

                # Create a new polling engine timer
                def do_poll(*args, **kwargs):
                    print('do_poll() interface.Update("{}", {})'.format(self._keepAliveQueryCommands[interface],
                                                                        self._keepAliveQueryQualifiers[interface]))
                    interface.Update(self._keepAliveQueryCommands[interface], self._keepAliveQueryQualifiers[interface])

                print('Creating new GSM do_poll Timer')
                new_timer = Timer(self._pollFreqs[interface], do_poll)
                new_timer.Stop()
                self._timers[interface] = new_timer

            else:  # assume keep_alive_query is a raw string. For Example: 'q' for querying extron fw

                # Delete any old polling engine timers
                if interface in self._timers:
                    self._timers[interface].Stop()
                    self._timers.pop(interface)

                # Create a new polling engine timer
                def do_poll(*args, **kwargs):
                    print('do_poll interface.Send({})'.format(self._keepAliveQueryCommands[interface]))
                    interface.Send(self._keepAliveQueryCommands[interface])

                print('Creating new raw do_poll Timer')
                new_timer = Timer(self._pollFreqs[interface], do_poll)
                self._timers[interface] = new_timer

        # Register ControlScript connection handlers
        self._assign_new_connection_handlers(interface)

        # Register module connection callback
        if hasattr(interface, 'SubscribeStatus'):

            if isinstance(interface, extronlib.interface.SerialInterface):
                self._update_connection_status_serial_or_ethernetclient(interface, 'Connected',
                                                                        'ControlScript1')  # SerialInterface ports are always 'Connected' in ControlScript
            self._check_send_methods(interface)
        else:
            # This interface is not an Extron module. We must create our own logical connection handling
            if isinstance(interface, extronlib.interface.EthernetClientInterface) or \
                    isinstance(interface, extronlib.interface.SerialInterface):
                self._add_logical_connection_handling_client(interface)

            elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
                self._add_logical_connection_handling_serverEx(interface)

        # At this point all connection handlers and polling engines have been set up.
        # We can now start the connection
        if hasattr(interface, 'Connect'):
            Wait(0, lambda i=interface: print('397 i.Connect res=', i.Connect(0.5)))
            # The update_connection_status method will maintain the connection from here on out.

    def _add_logical_connection_handling_client(self, interface):
        print('_add_logical_connection_handling_client')

        # Initialize the send counter to 0
        if interface not in self._send_counters:
            self._send_counters[interface] = 0

        self._check_connection_handlers(interface)
        self._check_send_methods(interface)
        self._check_rx_handler_serial_or_ethernetclient(interface)

        if isinstance(interface, extronlib.interface.SerialInterface):
            # SerialInterfaces are always connected via ControlScript.
            self._update_connection_status_serial_or_ethernetclient(interface, 'Connected', 'ControlScript2')

    def _check_connection_handlers(self, interface):
        print('UCH._check_connection_handlers')
        # if the user made their own connection handler, make sure our connection handler is called first
        if interface not in self._connected_handlers:
            self._connected_handlers[interface] = None

        if (interface.Connected != self._connected_handlers[interface] or
                interface.Disconnected != self._disconnected_handlers[interface]):
            self._assign_new_connection_handlers(interface)

        if hasattr(interface, 'SubscribeStatus'):
            try:
                oldSubscribeCallback = interface.Subscription.get('ConnectionStatus', {}).get('method', {}).get(
                    'callback', None)
            except:
                oldSubscribeCallback = None

            print('_check_connection_handlers oldSubscribeCallback=', oldSubscribeCallback)

            self._assign_new_connection_handlers(interface)

    def _assign_new_connection_handlers(self, interface):
        print('UCH._assign_new_connection_handlers')
        if interface not in self._connected_handlers:
            self._connected_handlers[interface] = None

        connection_handler = self._get_controlscript_connection_callback(
            interface
        )  # This line also saves the current user connected/disconnected handlers

        self._connected_handlers[interface] = connection_handler
        self._disconnected_handlers[interface] = connection_handler

        interface.Connected = connection_handler
        interface.Disconnected = connection_handler

        # Overwrite subscribe status if needed
        if hasattr(interface, 'SubscribeStatus'):
            try:
                print('interface.Subscription=', interface.Subscription)
                oldSubscribeCallback = interface.Subscription.get('ConnectionStatus', {}).get('method', {}).get(
                    'callback', None)
            except Exception as e:
                print('UCH Exception:', e)
                oldSubscribeCallback = None

            print('_assign_new_connection_handlers1 oldSubscribeCallback=', oldSubscribeCallback)

            if oldSubscribeCallback is not None:
                if oldSubscribeCallback.__module__ is not __name__:
                    print('_assign_new_connection_handlers2 oldSubscribeCallback=', oldSubscribeCallback)
                    newSubscribeCallback = self._get_module_connection_callback(interface)

                    def NewSubscribeCombined(c, v, q):
                        print('NewSubscribeCombined(c={}, v={}, q={})'.format(c, v, q))
                        newSubscribeCallback(c, v, q)
                        if callable(oldSubscribeCallback):
                            oldSubscribeCallback(c, v, q)

                    interface.SubscribeStatus('ConnectionStatus', None, NewSubscribeCombined)
                    print('after interface.SubscribeStatus=', NewSubscribeCombined)

            else:
                # The user's subscribe callback is None. Meaning the user didnt call .SubscribeStatus('ConnectionStatus')
                interface.SubscribeStatus('ConnectionStatus', None, self._get_module_connection_callback(interface))

    def _check_send_methods(self, interface):
        '''
        This method will check the .Send and .SendAndWait methods to see if they have already been replaced with the
            appropriate new_send that will also increment the self._send_counter
        :param interface:
        :return:
        '''

        self._check_connection_handlers(interface)

        if interface not in self._send_methods:
            self._send_methods[interface] = None

        if interface not in self._send_and_wait_methods:
            self._send_and_wait_methods[interface] = None

        current_send_method = interface.Send

        print('current_send_method=', current_send_method)
        print('current_send_method != self._send_methods[interface]=',
              current_send_method != self._send_methods[interface])
        print('current_send_method.__module__ is not __name__=', current_send_method.__module__ is not __name__)

        if current_send_method != self._send_methods[interface] and current_send_method.__module__ is not __name__:

            # Create a new .Send method that will increment the counter each time
            def new_send(*args, **kwargs):
                print('new_send args={}, kwargs={}'.format(args, kwargs))
                self._check_rx_handler_serial_or_ethernetclient(interface)
                self._check_connection_handlers(interface)

                currentState = self.get_connection_status(interface)
                print('new_send currentState=', currentState)
                if currentState is 'Connected':
                    self._send_counters[interface] += 1
                else:
                    # We dont need to increment the send counter if we know we are disconnected
                    pass
                print('new_send send_counter=', self._send_counters.get(interface, None))

                # Check if we have exceeded the disconnect limit
                if self._send_counters.get(interface, 0) > self._disconnectLimits.get(interface, 0):
                    # We have not received any responses after X sends, go disconnected
                    print('logical disconnect limit =', self._disconnectLimits[interface])
                    self._update_connection_status_serial_or_ethernetclient(interface, 'Disconnected', 'Logical4')
                else:
                    # Only send when connected
                    print(
                        'calling user_send_method {}(*args={}, **kwargs={})='.format(current_send_method, args, kwargs))
                    Wait(0, lambda a=args, k=kwargs: current_send_method(*a, **k))

            timer = self._timers.get(interface, None)
            if timer: timer.Start()

            interface.Send = new_send
            self._send_methods[interface] = new_send

        current_send_and_wait_method = interface.SendAndWait
        print('current_send_and_wait_method=', current_send_and_wait_method)
        if current_send_and_wait_method != self._send_and_wait_methods[
            interface] and current_send_and_wait_method.__module__ is not __name__:
            # Create new .SendAndWait that will increment the counter each time
            def new_send_and_wait(*args, **kwargs):
                print('new_send_and_wait args={}, kwargs={}'.format(args, kwargs))
                self._check_rx_handler_serial_or_ethernetclient(interface)
                self._check_connection_handlers(interface)

                self._send_counters[interface] += 1
                print('new_send_and_wait send_counter=', self._send_counters[interface])

                # Check if we have exceeded the disconnect limit
                if self._send_counters[interface] > self._disconnectLimits[interface]:
                    self._update_connection_status_serial_or_ethernetclient(interface, 'Disconnected', 'Logical2')

                try:
                    res = current_send_and_wait_method(*args, **kwargs)
                except (BrokenPipeError, TypeError, AttributeError) as e:
                    ProgramLog('new_send_and_wait(*args={}, **kwargs={})'.format(args, kwargs), 'warning')
                    ProgramLog(str(e), 'warning')
                    interface.Disconnect()
                    res = None

                if res not in [None, b'']:
                    self._send_counters[interface] = 0
                    print('res =', res, ', new_send_and_wait send_counter=', self._send_counters[interface])

                return res

            interface.SendAndWait = new_send_and_wait
            self._send_and_wait_methods[interface] = new_send_and_wait

    def _check_rx_handler_serial_or_ethernetclient(self, interface):
        '''
        This method will check to see if the rx handler is resetting the send counter to 0. if not it will create a new rx handler and assign it to the interface
        :param interface:
        :return:
        '''
        print('_check_rx_handler')

        if interface not in self._rx_handlers:
            self._rx_handlers[interface] = None

        current_rx = interface.ReceiveData
        if current_rx == None or (current_rx != self._rx_handlers[interface] and current_rx.__module__ is not __name__):
            # The Rx handler got overwritten somehow, make a new Rx and assign it to the interface and save it in self._rx_handlers
            def new_rx(*args, **kwargs):
                print('new_rx args={}, kwargs={}'.format(args, kwargs))
                self._send_counters[interface] = 0

                if isinstance(interface, extronlib.interface.EthernetClientInterface):
                    if not hasattr(interface, 'SubscribeStatus'):  # Rely on GSM's connection status
                        pass

                if callable(current_rx):
                    current_rx(*args, **kwargs)

            self._rx_handlers[interface] = new_rx
            interface.ReceiveData = new_rx
        else:
            # The current rx handler is doing its job. Moving on!
            pass

    def _add_logical_connection_handling_serverEx(self, interface):
        pass

    def _get_module_connection_callback(self, interface):
        # generate a new function that includes the interface and the 'kind' of connection
        def module_connection_callback(command, value, qualifier):
            print('module_connection_callback(command={}, value={}, qualifier={})'.format(command, value, qualifier))
            self._update_connection_status_serial_or_ethernetclient(interface, value, 'Module')

        return module_connection_callback

    def _destroyConnectionWait(self, interface):
        print('_destroyConnectionWait(interface={})'.format(interface))
        wt = self._connectWaits.pop(interface, None)  # remove the wait object
        print('613 wt=', wt)
        if wt is not None:
            print('615 wt.Cancel() wt=', wt)
            wt.Cancel()

    def _get_controlscript_connection_callback(self, interface):

        if isinstance(interface, extronlib.interface.EthernetClientInterface):
            print('_get_controlscript_connection_callback(interface={})'.format(interface))
            print('interface.Connected=', interface.Connected)
            print('interface.Disconnected=', interface.Disconnected)
            print('self._user_connected_handlers[interface]=', self._user_connected_handlers.get(interface, 'KeyError'))
            print('self._user_disconnected_handlers[interface]=',
                  self._user_disconnected_handlers.get(interface, 'KeyError'))
        # generate a new function that includes the 'kind' of connection

        # init some values
        if interface not in self._connected_handlers:
            self._connected_handlers[interface] = None

        if interface not in self._disconnected_handlers:
            self._disconnected_handlers[interface] = None

        if interface not in self._user_connected_handlers:
            self._user_connected_handlers[interface] = None

        if interface not in self._user_disconnected_handlers:
            self._user_disconnected_handlers[interface] = None

        # Get handler

        # save user Connected handler
        callback = getattr(interface, 'Connected')  # SerialInterface does not have 'Connected' attribute

        if callback != self._connected_handlers[interface]:
            if callback is not None:
                if callback.__module__ is not __name__:
                    # The connection handler was prob overridden in main.py. Reassign it
                    self._user_connected_handlers[interface] = callback

                    # If the user changes the userCallback, call the userCallback with the current state
                    if IsConnected(interface):
                        print('616 calling _user_connected_handlers')
                        self._user_connected_handlers[interface](interface, 'Connected')
        else:
            if callback is None:
                self._user_connected_handlers[interface] = None

        # save user Disconnected handler
        callback = getattr(interface, 'Disconnected')  # SerialInterface does not have 'Disconnected' attribute

        if callback is not None:
            print('disconnectCallback=', callback)
            print('self._disconnected_handlers[interface]=', self._disconnected_handlers[interface])
            print('callback.__module__=', callback.__module__)
            print('__name__=', __name__)
            print('callback != self._disconnected_handlers[interface]=',
                  callback != self._disconnected_handlers[interface])
            print('callback.__module__ is not __name__=', callback.__module__ is not __name__)

        if callback != self._disconnected_handlers[interface]:
            if callback is not None:
                if callback.__module__ is not __name__:
                    # The connection handler was prob overridden in main.py. Reassign it
                    self._user_disconnected_handlers[interface] = callback

                    # If the user changes the userCallback, call the userCallback with the current state to make sure the user is notified of the current state
                    if not IsConnected(interface):
                        print('648 Calling user disconnected handler', self._connection_status)
                        self._user_disconnected_handlers[interface](interface, 'Disconnected')
        else:
            if callback is None:
                self._user_disconnected_handlers[interface] = None

        # Create the new handler
        if isinstance(interface, extronlib.interface.EthernetClientInterface):
            def controlscript_connection_callback(intf, state):
                print(
                    'extronlib.interface controlscript_connection_callback(intf={}, state={}) self._connectWaits={}'.format(
                        intf, state, self._connectWaits))

                if state == 'Connected':
                    self._destroyConnectionWait(intf)

                # If we receive a graceful disconnect from the server, also disconnect module
                # try:
                #     currentModuleState = intf.ReadStatus('ConnectionStatus')
                #     if currentModuleState != state:
                #         if state == 'Connected':
                #             intf.OnConnected()
                #             pass
                #         elif state == 'Disconnected':
                #             intf.OnDisconnected()
                # except:
                #     pass

                self._update_connection_status_serial_or_ethernetclient(intf, state,
                                                                        'ControlScript4')  # Also calls user connection callback
        else:
            controlscript_connection_callback = None

        print('end self._user_connected_handlers[interface]=',
              self._user_connected_handlers.get(interface, 'KeyError'))
        print('end self._user_disconnected_handlers[interface]=',
              self._user_disconnected_handlers.get(interface, 'KeyError'))

        return controlscript_connection_callback

    def get_connection_status(self, interface):
        # return 'Connected' or 'Disconnected'
        # Returns None if this interface is not being handled by this UCH
        return self._connection_status.get(interface, None)

    def _get_serverEx_connection_callback(self, parent):
        '''
        Stores the current user callback
        Creates a new callback that adds CH functionality and then calls the user callback.
        :param parent:
        :return:
        '''

        if parent.Connected is None or \
                parent.Connected.__module__ is not __name__:
            # The current parent.Connected is from a diff module and probaly the user callback
            # Store it for later
            self._user_connected_handlers[parent] = parent.Connected

        if parent.Disconnected is None or \
                parent.Disconnected.__module__ is not __name__:
            # The current parent.Disconnected is from a diff module and probaly the user callback
            # Store it for later
            self._user_disconnected_handlers[parent] = parent.Disconnected

        def controlscript_connection_callback(client, state):
            print('serverEx controlscript_connection_callback(client={}, state={})'.format(client, state))
            print('self._user_connected_handlers=', self._user_connected_handlers)
            print('self._user_disconnected_handlers=', self._user_disconnected_handlers)

            if state == 'Connected':
                if parent in self._user_connected_handlers:
                    if callable(self._user_connected_handlers[parent]):
                        print('778 calling _user_connected_handlers')
                        self._user_connected_handlers[parent](client, state)

            elif state == 'Disconnected':
                if parent in self._user_disconnected_handlers:
                    if callable(self._user_disconnected_handlers[parent]):
                        self._user_disconnected_handlers[parent](client, state)

            self._update_connection_status_server(parent, client, state, 'ControlScript5')

        return controlscript_connection_callback

    def _update_connection_status_server(self, parent, client, state, kind=None):
        '''
        This method will save the connection status and trigger any events that may be associated
        :param parent: EthernetServerInterfaceEx object
        :param client: ClientObject
        :param state: 'Connected' or 'Disconnected'
        :param kind: 'ControlScript' or 'Logical'
        :return:
        '''

        if state == 'Connected':
            client.Parent = parent  # Add this attribute to the client object for later reference

            if parent not in self._server_client_rx_timestamps:
                self._server_client_rx_timestamps[parent] = {}

            self._server_client_rx_timestamps[parent][
                client] = time.monotonic()  # init the value to the time the connection started
            self._check_rx_handler_serverEx(client)

            if callable(self._connected_callback):
                self._connected_callback(client, state)

        elif state == 'Disconnected':
            self._remove_client_data(client)  # remove dead sockets to prevent memory leak

            if callable(self._disconnected_callback):
                self._disconnected_callback(client, state)

        self._update_serverEx_timer(parent)

        self._log_connection_to_file(client, state, kind)

    def _check_rx_handler_serverEx(self, client):
        '''
        Every time data is recieved from the client, set the timestamp
        :param client:
        :return:
        '''
        print('_check_rx_handler_serverEx(client=', client)
        parent = client.Parent

        if parent not in self._rx_handlers:
            self._rx_handlers[parent] = None

        old_rx = parent.ReceiveData
        if self._rx_handlers[parent] != old_rx or (old_rx == None):
            # we need to override the rx handler with a new handler that will also add the timestamp
            def new_rx(client, data):
                time_now = time.monotonic()
                print('new_rx time_now={}, client={}, data={}'.format(time_now, client, data))
                self._server_client_rx_timestamps[parent][client] = time_now
                self._update_serverEx_timer(parent)
                if callable(old_rx):
                    old_rx(client, data)

            parent.ReceiveData = new_rx
            self._rx_handlers[parent] = new_rx

    def _update_serverEx_timer(self, parent):
        '''
        This method will check all the time stamps and set the timer so that it will check again when the oldest client
            is near the X minute timeout mark.
        :param parent:
        :return:
        '''
        print('_update_serverEx_timer parent=', parent)
        print(' len(parent.Clients)=', len(parent.Clients))
        if len(parent.Clients) > 0:
            print('self._server_client_rx_timestamps[parent]=', self._server_client_rx_timestamps[parent])
            oldest_timestamp = None
            for client, client_timestamp in self._server_client_rx_timestamps[parent].copy().items():

                if (oldest_timestamp is None) or client_timestamp < oldest_timestamp:
                    oldest_timestamp = client_timestamp

                print('client={}, client_timestamp={}, oldest_timestamp={}, nowtime={}'.format(
                    client,
                    client_timestamp,
                    oldest_timestamp,
                    time.monotonic(),
                ))

            # We now have the oldest timestamp, thus we know when we should check the client again

            if oldest_timestamp is not None:
                seconds_until_timer_check = self._connection_timeouts[parent] - (time.monotonic() - oldest_timestamp)
                if seconds_until_timer_check > 0:
                    print('seconds_until_timer_check=', seconds_until_timer_check)
                    print('len(parent.Clients)=', len(parent.Clients))
                    self._timers[parent].ChangeTime(seconds_until_timer_check)
                    self._timers[parent].Start()

            # Lets say the parent timeout is 5 minutes.
            # If the oldest connected client has not communicated for 4min 55sec, then seconds_until_timer_check = 5 seconds
            # The timer will check the clients again in 5 seconds.
            # Assuming the oldest client still has no communication, it will be disconnected at the 5 minute mark exactly

        else:  # there are no clients connected
            print('870 Timer.Stop()')
            self._timers[parent].Stop()

    def _disconnect_undead_clients(self, parent):
        print('_disconnect_undead_clients')
        for client in parent.Clients:
            client_timestamp = self._server_client_rx_timestamps[parent].get(client, None)
            if client_timestamp is None:
                continue

            if time.monotonic() - client_timestamp > self._connection_timeouts[parent]:
                if client in parent.Clients:
                    if debug:
                        client.Send(time.asctime() + ' ')

                    print('Disconnected client=', client)

                    client.Send('Disconnecting due to inactivity for {} seconds.\r\nBye.\r\n'.format(
                        self._connection_timeouts[parent])
                    )

                    client.Disconnect()

                self._remove_client_data(client)

        self._update_serverEx_timer(parent)

    def _remove_client_data(self, client):
        # remove dead sockets to prevent memory leak
        print('_remove_client_data client=', client)
        self._server_client_rx_timestamps[client.Parent].pop(client, None)

    def _log_connection_to_file(self, interface, state, kind):
        print('_log_connection_to_file(interface={}, state={}, kind={})'.format(interface, state, kind))

        if 'ControlScript' in kind:
            if self._logPhysicalConnection[interface]:
                self._do_log_connection_to_file(interface, state, kind)

        elif 'Module' in kind or 'Logical' in kind:
            if self._logLogicalConnection[interface]:
                self._do_log_connection_to_file(interface, state, kind)

    def _do_log_connection_to_file(self, interface, state, kind):

        # Write new status to a file
        with File(self._filename, mode='at') as file:
            write_str = '{}\n    {}:{}\n'.format(time.asctime(), 'type', type(interface))
            write_str += '    {}:{}\n'.format('id', id(interface))

            for att in [
                'IPAddress',
                'IPPort',
                'DeviceAlias',
                'Port',
                'Host',
                'ServicePort',
                'Protocol',
            ]:
                if hasattr(interface, att):
                    write_str += '    {}:{}\n'.format(att, getattr(interface, att))

                    if att == 'Host':
                        write_str += '    {}:{}\n'.format('Host.DeviceAlias', getattr(interface, att).DeviceAlias)

            write_str += '    {}:{}\n'.format('ConnectionStatus', state)
            write_str += '    {}:{}\n'.format('Kind', kind)

            file.write(write_str)
            file.close()

    def _update_connection_status_serial_or_ethernetclient(self, interface, state, kind=None):
        '''
        This method will save the connection status and trigger any events that may be associated
        :param interface:
        :param state: str
        :param kind: str() 'ControlScript' or 'Module' or any other value that may be applicable
        :return:
        '''
        print('_update_connection_status_serial_or_ethernetclient(interface={}, state={}, kind={})'.format(
            interface,
            state,
            kind,
        ))

        if interface not in self._connection_status:
            self._connection_status[interface] = 'Unknown'

        if state == 'Connected':
            self._send_counters[interface] = 0

        print('oldConnectionStatus=', self._connection_status[interface])
        print('newConnectionStatus=', state)
        if state != self._connection_status[interface]:
            # The state has changed. Do something with that change

            print('Connection status has changed for interface={} from "{}" to "{}"'.format(
                interface,
                self._connection_status[interface],
                state,
            ))

            # save the state for later
            self._connection_status[interface] = state

            print('UCH.Connected=', self._connected_callback)
            print('UCH.Disconnected=', self._disconnected_callback)

            print('interface.Connected=', interface.Connected)
            print('interface.Disconnected=', interface.Disconnected)

            if state == 'Connected':
                if callable(self._connected_callback):
                    self._connected_callback(interface, state)

            elif state == 'Disconnected':
                if callable(self._disconnected_callback):
                    self._disconnected_callback(interface, state)

            self._log_connection_to_file(interface, state, kind)

            # Do the user's callback function
            print('self._user_connected_handlers=', self._user_connected_handlers)
            print('self._user_disconnected_handlers=', self._user_disconnected_handlers)

            if state == 'Connected':
                if interface in self._user_connected_handlers:
                    if callable(self._user_connected_handlers[interface]):
                        print('998 calling _user_connected_handlers')
                        self._user_connected_handlers[interface](interface, state)

            elif state == 'Disconnected':
                if interface in self._user_disconnected_handlers:
                    if callable(self._user_disconnected_handlers[interface]):
                        self._user_disconnected_handlers[interface](interface, state)

        # if the interface is disconnected, try to reconnect
        if state == 'Disconnected':
            self._send_counters[interface] = 0

            print('Currently Disconnected. Should try to reconnect')
            if hasattr(interface, 'Connect'):
                print('1026 self._connectWaits.get(interface, None)=', self._connectWaits.get(interface, None))
                if self._connectWaits.get(interface, None) is None:
                    print('Trying to re-connect to interface={}'.format(interface))

                    def ReconnectWaitFunc(interface=interface):
                        print('1035 ReconnectWaitFunc interface=', interface)
                        self._destroyConnectionWait(interface)
                        print('1032 _connectWaits {} result={}'.format(interface, interface.Connect()))

                    wt = Wait(self._connectionRetryFreqs[interface], ReconnectWaitFunc)

                    print('1046 reconnect wt=', wt, ', interface=', interface)
                    self._connectWaits[interface] = wt
                else:
                    print('interface.Connect in progress. Waiting for timeout or successful connection')

            # If a TCP interface is logically disconnect, also do physical disconnect.
            if state == 'Disconnected':
                if 'Logical' in kind or 'Module' in kind:
                    if isinstance(interface, extronlib.interface.EthernetClientInterface):
                        interface.Disconnect()  # do physical disconnect

        # Start/Stop the polling timer if it exists
        if interface in self._timers:
            if state == 'Connected':
                print(
                    '_update_connection_status_serial_or_ethernetclient calling Timer.Start() self._timers[interface]=',
                    self._timers[interface])
                self._timers[interface].Start()

            elif state == 'Disconnected':
                if isinstance(interface, extronlib.interface.SerialInterface):
                    # SerialInterface has no Disconnect() method so the polling engine is the only thing that can detect a re-connect.
                    # Keep the timer going.
                    pass

                elif isinstance(interface, extronlib.interface.EthernetClientInterface):
                    print('Stopping do_poll() Timer')
                    self._timers[interface].Stop()
                    # Stop the timer and wait for a 'Connected' Event

    def __str__(self):
        s = '''{}\n\n***** Interfaces being handled *****\n\n'''.format(self)

        for interface in self._interfaces:
            s += self._interface_to_str(interface)

    def __repr__(self):
        return str(self)

    def _interface_to_str(self, interface):
        write_str = '{}\n'.format(self)

        for att in [
            'IPAddress',
            'IPPort',
            'DeviceAlias',
            'Port',
            'Host',
            'ServicePort',
        ]:
            if hasattr(interface, att):
                write_str += '    {}:{}\n'.format(att, getattr(interface, att))
            write_str += '    {}:{}'.format('Connection Status', self._connection_status[interface])

        return write_str

    @property
    def Connected(self):
        '''
        There will be a single callback that will pass two params, the interface and the state
        :return:
        '''
        return self._connected_callback

    @Connected.setter
    def Connected(self, callback):
        print('UCH.Connected.setter callback={}'.format(callback))
        self._connected_callback = callback

    @property
    def Disconnected(self):
        '''
        There will be a single callback that will pass two params, the interface and the state
        :return:
        '''
        return self._disconnected_callback

    @Disconnected.setter
    def Disconnected(self, callback):
        print('UCH.Disconnected.setter callback={}'.format(callback))
        self._disconnected_callback = callback


class Timer:
    def __init__(self, t, func):
        t = 0 if t < 0 else t
        print('Timer.__init__(t={}, func={}, self={}'.format(t, func, self))
        self._t = t
        self._func = func
        self._eWait = Wait(self._t, self._Expired)
        self._running = True

    def Start(self):
        print('Timer.Start() _func={}, eWait.Time={}, self={}'.format(self._func, self._eWait.Time, self))
        self._running = True

        #self._eWait.Restart()
        self._eWait.Cancel()
        self._eWait = Wait(self._t, self._Expired) # getting a "set to this timer already' error using .Restart() so trying this instead

    def ChangeTime(self, newTime):
        print('Timer.ChangeTime(newTime={}) _func={}, self={}'.format(newTime, self._func, self))
        newTime = 0 if newTime < 0 else newTime
        self._eWait.Cancel()
        self._t = newTime
        self._eWait = Wait(self._t, self._Expired)
        print('Timer._eWait.Time=', self._eWait.Time)

    def Stop(self, *args, **kwargs):
        print('Timer.Stop() _func={}, eWait.Time={}, self={}'.format(self._func, self._eWait.Time, self))
        self._running = False
        self._eWait.Cancel()
        print('eWait.Cancel complete')

    def _Expired(self):
        # called when eWait expires
        print('Timer._Expired() _func={}, eWait.Time={}, self={}'.format(self._func, self._eWait.Time, self))
        if self._running:
            self._func()

        if self._running:
            print('Expired calling Start() _func={}, self={}'.format(self._func, self))
            self.Start()

    def __del__(self):
        self.Stop()


__all__ = ('HandleConnection', 'IsConnected', 'GetInterfaces')
