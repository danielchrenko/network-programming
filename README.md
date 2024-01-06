# Network Programming Projects

All of these programs were used on PicoNet in order to simulate network conditions

## sws.py

To run:
python3 sws.py ip_address port_number

Use netcat (nc sws_ip_address sws_port_number) to connect and you can now use commands such as /GET etc used in standard HTTP req
-> will elaborate further 

sws was a mock HTTP server that provides a service for persistent on non persistent connections.

Provides feedback depending on requests
-bad_request = "HTTP/1.0 400 Bad Request\r\n"
-file_incorrect = "HTTP/1.0 404 Not Found\r\n"
-good_request = "HTTP/1.0 200 OK\r\n"

Utilizes python socket/select libraries to send and receive requests/responses across network with multiple clients.

## rdp.py

To run:
python3 rdp.py ip_address port_number read_file_name write_file_name

Although you could just pass the data through the program itself (this program is a bit redundant) basically removing the need for any network communication
it provids a backbone to the sor-client + sor-server in the next project

This was a project meant to simulate a reliable data protocol (rdp)

Notes: this project uses ack and syn etc but does not follow the exact behaviour as TCP
-(slightly altered version of different flag values in order make debugging easier but stil provide same info ordering wise)

implements techniques such as:
-go-back-n 
-acknowledgement numbers 
-sequence numbers 
-congestion window

this is to provide a reliable connection that can operate with packet loss, and still allows receiver to not get a overflowed buffer and process data in order.

## sor-client.py + sor-server.py

implements the mock HTTP server USING the RDP made in project 2

uses all the above things mentioned in order to achieve this

client can make requests 