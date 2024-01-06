import socket
import select
import sys
import queue
import time
import re
import os


snd_buf = queue.Queue()
rcv_buf = queue.Queue()
rcv_packet_queue = queue.Queue()
# buffers

rf = sys.argv[3]
wf = sys.argv[4]
# files

read_handle = open(rf, 'r')
write_handle = open(wf, 'w')
# file handles

echo = ("10.10.1.100", 8888)
# echo server

def main():
    
    rdp_s = rdp_sender()
    rdp_r = rdp_receiver()
    rdp_s.open()
    
    ip_address = sys.argv[1]
    port_number = int(sys.argv[2])
    server_address = (ip_address, port_number)
    # setup of server address based off of input
    
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(server_address)
    # sock dgram because datagram socket because udp and bind


    while True:
        
        readable, writable, exceptional = select.select([udp_sock], [udp_sock], [udp_sock])
        
        if udp_sock in readable:
            
            message = udp_sock.recv(1024)
            full_message = message.decode()
            lines = full_message.split('\r\n')
            
            for line in lines:
                rcv_buf.put(line)
                
            buffer_to_packet_queue()
            # now extracted the packets line by line
            
            try:
                packet = rcv_packet_queue.get_nowait()
                
                if packet.command == 'ACK':
                    rdp_s.rcv_ack(packet)
                    # packet is an ack
                else:
                    rdp_r.rcv_data(packet)
                    # packet is NOT an ack filter to rcv
            
            except queue.Empty:
                pass
            
             
        if udp_sock in writable:
            
            try:
                packet = snd_buf.get_nowait()
                packet_message = str(packet).encode()
                bytes_sent = udp_sock.sendto(packet_message, echo)
                log('Send', packet)
                
            except queue.Empty:
                pass
            
        if (rdp_s.state == 'closed' and rdp_r.state == 'closed'):
            exit()
                  

    
class rdp_sender:
    ''' class for rdp_sender
    
    closed -> syn-sent -> open -> fin-sent -> closed
    '''
    def __init__(self):
        
        self.state = 'closed'
        self.ack = 0
        self.sent = 0
        self.file_size = os.path.getsize(rf)
        self.window = 0
        self.length = 500 # can choose packet length here
        self.count = 0
        
    def __send(self):
        
        if self.state == 'syn-sent':
            # write syn rdp packet into snd_buf
            syn_packet = rdp_packet('SYN', 'Sequence: 0', 'Length: 0', '')
            snd_buf.put(syn_packet)
            self.ack += 1 # next expected ack number
            
            
        elif self.state == 'open':
            # write the available window of DAT rdp packets into snd_buf
            
            if self.sent == self.file_size:
                self.close()
                
            elif self.window > self.length:
                # window has room for at least 1 packet
                    
                if self.sent + self.length < self.file_size:
                    # enough room for 1 pack
                    self.sent += self.length
                    data_string = ''
                    data_string += read_handle.read(self.length)
                    dat_packet = rdp_packet('DAT','Sequence: ' + str(self.ack), 'Length: ' + str(self.length), data_string)
                    self.ack += self.length
                    snd_buf.put(dat_packet)
                    

                elif self.sent < self.file_size:
                    length = self.file_size - self.sent
                    self.sent += length
                    data_string = ''
                    data_string += read_handle.read(length)
                    dat_packet = rdp_packet('DAT', 'Sequence: ' + str(self.ack), 'Length: ' + str(length), data_string)
                    self.ack += length
                    snd_buf.put(dat_packet)
                    
  
        elif self.state == 'fin-sent':
            # write the fin rdp packet into snd_buf
            fin_packet = rdp_packet('FIN', 'Sequence: ' + str(self.ack), 'Length: 0', '')
            snd_buf.put(fin_packet)
            self.ack += 1 # next expected ack number
    
    
    def open(self):
        
        self.state = 'syn-sent'
        self.__send()
        
    def rcv_ack(self, packet):
        
        self.count += 1
        
        if packet.get_sa() == self.ack:
        
            if self.state == 'syn-sent':

                    log('Receive', packet)
                    self.state = 'open'
                    self.window = packet.get_wl()
                    self.__send()

            elif self.state == 'open':

                    log('Receive', packet)
                    self.window = packet.get_wl()
                    self.__send()
                    # need to move the sliding window also

            elif self.state == 'fin-sent':

                    log('Receive', packet)
                    self.state = 'closed'
                    write_handle.close()
                    read_handle.close()
            
    def timeout(self, packet, resolve_ack):
        if not self.state == 'close':
            pass
    
    def close(self):
        self.state = 'fin-sent'
        self.__send()
    
    
    
    
class rdp_receiver:
    ''' rdp_receiver class
    '''
    def __init__(self):
        self.ack = 0
        self.window = 5000 # 10 packets
        self.state = 'open'

        
    def rcv_data(self, packet):

        if packet.command == 'SYN':

            if packet.get_sa() == self.ack:

                log('Receive', packet)
                self.ack += 1
                ack_packet = rdp_packet('ACK', 'Acknowledgement: ' + str(self.ack), 'Window: ' + str(self.window), '')
                snd_buf.put(ack_packet)

        if packet.command == 'FIN':

            if packet.get_sa() == self.ack:

                log('Receive', packet)
                self.ack += 1
                ack_packet = rdp_packet('ACK', 'Acknowledgement: ' + str(self.ack), 'Window: ' + str(self.window), '')
                snd_buf.put(ack_packet)
                self.state = 'closed'

        if packet.command == 'DAT':

            self.window -= packet.get_wl()

            if packet.get_sa() == self.ack:

                log('Receive', packet)
                self.ack += packet.get_wl()

                write_to_file(packet)

                self.window += packet.get_wl()
                # write to file, so free window, (static window without delay/loss)

                ack_packet = rdp_packet('ACK', 'Acknowledgement: ' + str(self.ack), 'Window: ' + str(self.window), '')

                snd_buf.put(ack_packet)

            else:

                log('ADDED TO WINDOW BUFFER', packet)
                    
                

    
class rdp_packet:
    ''' class for rdp_packet
    
    command, seq/ack, window/length, data (if any)
    '''
    def __init__(self, command, sa, wl, data):
        self.command = command
        self.sa = sa
        self.wl = wl
        self.data = data
    
    def __str__(self):
        str_form = self.command + '\r\n' + self.sa + '\r\n' + self.wl + '\r\n'
        if self.data:
            str_form += '\r\n' + self.data
        return str_form
    
    def __lt__(self, other):
        return self.sa < other.sa
            
    def log_form(self):
        log_string = self.command + '; ' + self.sa + '; ' + self.wl
        return log_string
    
    def get_sa(self):
        temp = self.sa.split(':')
        return int(temp[1]) 
    
    def get_wl(self):
        temp = self.wl.split(':')
        return int(temp[1])  
        
        

        
def log(event, packet):
    ''' log function
    
    input: event and packet
    output: prints the log for the packet in the terminal
    '''
    timestamp = time.strftime('%a %b %d %H:%M:%S ' + 'PDT' + ' %Y: ' ,time.localtime())
    print(timestamp + event + '; ' + packet.log_form())

    
    
def write_to_file(packet):
    ''' write to file function
    '''
    write_handle.write(packet.data)

    
    
    
def buffer_to_packet_queue():
    ''' buffer_to_packets Function
    
    This function handles and partitions string in the receiveer buffer
    packet construction steps 1: command, 2: headers, 3: PAYLOAD 4: done send packet 0: not made anything yet
    '''
    commands = ['SYN', 'FIN', 'DAT', 'ACK', 'RST']
    # commands that can be headers
    
    while rcv_buf:

        try:
            # keep going through buffer until empty
            line = rcv_buf.get_nowait()
            # pop first line in buffer

            if line in commands:
                command = ''
                sa = ''
                wl = ''
                data = ''
                # contents of the packet

                command = line
                # is command line so put line as command

                line = rcv_buf.get_nowait()

                if not re.findall(r'[a-zA-Z]+:\s[0-9]+', line):
                    continue
                    # go back to start of while loop if header does not match format

                if "Sequence:" in line:
                    sa = line
                    
                    line = rcv_buf.get_nowait()
                    if "Length:" in line:
                        wl = line
                        
                        temp = line.split(':')
                        
                        if not int(temp[1]) == 0:
                            
                            line = rcv_buf.get_nowait()
                            
                            if line == "":
                                line = rcv_buf.get_nowait()

                                data = line
                                
                                rcv_packet_queue.put(rdp_packet(command, sa, wl, data))
                                # make a packet tuple with all the info
                                
                        else:
                            
                            rcv_packet_queue.put(rdp_packet(command, sa, wl, data))
                            continue

                        
                if "Acknowledgement:" in line:
                    sa = line
                    
                    line = rcv_buf.get_nowait()

                    if "Window:" in line:
                        wl = line
                        
                        rcv_packet_queue.put(rdp_packet(command, sa, wl, ''))
                
            
        except queue.Empty:
            # queue empty so break
            break


            
# standard Python boilerplate
if __name__ == '__main__':
    main()