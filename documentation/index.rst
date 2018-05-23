.. Connection Handler documentation master file, created by
   sphinx-quickstart on Thu Feb 15 08:42:52 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to the Connection Handler documentation!
========================================================

This module provides automatic handling of the following type of interface connections:

* Serial
* TCP
* SSH
* TCP Server (using extronlib.interface.EthernetServerEx)
* Extron GS Device Modules (Using the above protocols)

==========================================
Minimum Software and Firmware Requirements
==========================================

.. list-table::
    :widths: 30 70

    * - **Extron Library API**
      - 2.6r19
    * - **IPL Pro Firmware**
      - 2.08
    * - **GS Version**
      - 1.4.2

===============
Version History
===============

.. list-table::
    :widths: 10 10 80
    :header-rows: 1

    * - Version
      - Date
      - Description
    * - 1.0.0
      - 2/16/2018
      - Initial Version.


=========
Functions
=========

.. py:module:: connection_handler.py

.. py:function:: HandleConnection(interface)

	Calling this function will maintain the connection to the *interface*. You may want to implement your own polling or use the connection handlers polling (*keepAliveQueryCommand*)

    :param interface: This is the only required parameter.
    :type interface: extronlib.interface.* or extronlib.device.*

    :param keepAliveQueryCommand: (optional parameter) If *interface* is an Extron GSM, a string like *'Power'* will cause the connection handler to poll with *interface.Update('Power')*. If *interface is any other extronlib.interface.** object, the connection handler will poll with *interface.Send('Power')*
    :type keepAliveQueryCommand: str

    :param keepAliveQueryQualifier: (optional parameter) If *interface* is an Extron GSM, this will be the qualifier used to poll. For example if *keepAliveQueryCommand='Power'* and *keep_alive_query_qual={'ID': '1'}*, the connection handler will poll with *interface.Update('Power', {'ID': '1'})*
    :type keepAliveQueryQualifier: dict

    :param pollFreq: (optional parameter) How many seconds between poll commands. This is only used if *keepAliveQueryCommand* is passed also. If no value for *poll_freq* is passed, a default value of 5 seconds is used.
    :type pollFreq: float/int

    :param disconnectLimit: (optional parameter) This is the logical disconnect limit. This means that the connection handler will report *Disconnected* when it has sent *disconnect_limit* number of messages and not received any responses. Note: Extron GSMs may also have a disconnect limit. The connection handler will report *Disconnected* from both the *disconnect_limit* and the Extron GSM logical disconnection. Whichever happens first.
    :type disconnectLimit: int

    :param serverTimeout: (optional parameter) This is only used when *interface* is an instance of *extronlib.interface.EthernetServerInterfaceEx*. The server will automatically disconnect any clients that have not sent any messages to the server for *server_timeout* seconds. The server will also send a message to the client indicating it has been disconnected due to inactivity for X seconds. If no *server_timeout* parameter is passed to the *HandleConnection* function, a default value of 300 seconds (5 minutes) is used.
    :type serverTimeout: float/int

    :param connectionRetryFreq: (optional parameter) This indicates how many seconds between when an *interface* is disconnected, and the connection handler tries to reconnect. If no *connection_retry_freq* parameter is passed, a default value of 5 seconds is used.
    :type connectionRetryFreq: float/int

    :param logPhysicalConnection: (optional parameter) This indicates whether to log physical connection events (*interface.Connected* and *interface.Disconnected*) to the log file created in the SFTP file space.If no *log_physical_connection* parameter is passed, the defaul action is to log the events (*True*).
    :type logPhysicalConnection: bool

    :param logLogicalConnection: (optional parameter) This indicates whether to log logical connection events (*interface.SubscribeStatus('ConnectionStatus')*) to the log file created in the SFTP file space.If no *log_logical_connection* parameter is passed, the defaul action is to log the events (*True*).
    :type logLogicalConnection: bool

    :return: The default handler.
    :rtype: *connection_handler.UniversalConnectionHandler*

.. py:function:: IsConnected(interface)

	Use this function to check the current connection status of an *interface*

    :param interface: This interface must have been previously passed to the *HandleConnection()* function.
    :type interface: extronlib.interface.* or extronlib.device.*

    :return: *True* if *interface* is currently connected. *False* otherwise.
    :rtype: bool

.. py:function:: GetAllDefaultHandlerInterfaces()

	Get all the *interface*'s that have been passed to *HandleConnection()*.

    :return: list of *interface* objects
    :rtype: list


Code Example
============

.. code-block:: python
    :linenos:

	from extronlib.interface import EthernetClientInterface
	from extronlib import event
	from connection_handler import HandleConnection, IsConnected

	client = EthernetClientInterface('1.8.8.5', 3888)
	HandleConnection(client)

	# There are several other options you can pass in HandleConnection() for clients/servers, but none are required.

	#You can also check the connection status at any time like this
	if IsConnected(client):
	    print('The client is connected')
	else:
	    print('The client is not connected')

	#You can also still use connection events normally
	@event(client, ['Connected', 'Disconnected'])
	def ClientConnectionEvent(interface, state):
	    print('The client is {}.'.format(state))

	#You can also still use ReceiveData events normally
	@event(client, 'ReceiveData')
	def ClientRxEvent(interface, data):
	    print('Rx:', data)


Since *extronlib.interface.SerialInterface* objects do not have a *'Connected'* event, you can use the default handler like so

.. code-block:: python
    :emphasize-lines: 10,12
    :linenos:

    from extronlib.interface import SerialInterface
    from extronlib.device import ProcessorDevice
    from extronlib import event

    from connection_handler import HandleConnection

    proc = ProcessorDevice('ProcessorAlias')
    client = SerialInterface(proc, 'COM1', Baud=38400)

    handler = HandleConnection(client, keepAliveQueryCommand='q')

    @event(handler, ['Connected', 'Disconnected'])
    def ClientConnectionEvent(interface, state):
        print('ClientConnectionEvent(interface={}, state={})'.format(interface, state))

    @event(client, 'ReceiveData')
    def ClientRxEvent(interface, data):
        print('Rx data=', data)

If using a *SerialClass* from an Extron GSM, you can use *SubscribeStatus* normally.

.. code-block:: python
    :emphasize-lines: 14
    :linenos:

    from extronlib.device import ProcessorDevice
    from extronlib import event
    import extr_dsp_DMP64_v1_2_0_0 as DMP_Module
    from connection_handler import HandleConnection

    proc = ProcessorDevice('ProcessorAlias')
    client = DMP_Module.SerialClass(proc, 'COM1', Baud=38400)

    HandleConnection(client, keepAliveQueryCommand='PartNumber')

    def ClientConnectionEvent(*args, **kwargs):
        print('ClientConnectionEvent(args={}, kwargs={})'.format(args, kwargs))

    client.SubscribeStatus('ConnectionStatus', None, ClientConnectionEvent)

