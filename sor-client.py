import socket
import select
import sys
import queue
import time
import re
import os

# input: 
# python3 sor-client.py server_ip_address server_udp_port_number server_buffer_size server_payload_length read_file_name write_file_name

# tests
# python3 sor-client.py 10.10.1.100 8888 5120 1024 rf.txt wf.txt
# python3 sor-client.py 10.10.1.100 8888 5120 1024 rf.txt wf.txt rf2.txt wf2.txt

snd_buf = queue.Queue()
rcv_buf = queue.Queue()
packet_buf = queue.Queue()
# message queues (need to be global)
# not a dictionary since this is the client

client_buffer_size = sys.argv[3]
client_payload_length = sys.argv[4]

read_files = []
write_files = []

def main():

    ip_address = sys.argv[1]
    port_number = int(sys.argv[2])
    server_address = (ip_address, port_number)
    # server address to connect to

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # initialization
    
    # new instance of RDP class
    rdp_instance = rdp_class()
    rdp_instance.send_syn()
    
    while True:

        readable, writable, exceptional = select.select([udp_sock], [udp_sock], [udp_sock])

        if udp_sock in readable:
            
            message = udp_sock.recv(2048)
            full_message = message.decode()
            lines = full_message.split('\r\n')
            
            for line in lines:
                rcv_buf.put(line)
                
            buffer_to_packet()
            
            try:
                packet = packet_buf.get_nowait()
                # print(packet.data)
                rdp_instance.rcv_pack(packet)
            
            except queue.Empty:
                pass
                
        
        if udp_sock in writable:
            
            try:
                packet = snd_buf.get_nowait()
                packet_message = str(packet).encode()
                bytes_sent = udp_sock.sendto(packet_message, server_address)
                packet.log('Send')
                if rdp_instance.state == 'close':
                    exit()
            
            except queue.Empty:
                pass

            
            
            
class rdp_packet:
    ''' class for rdp_packet
    
    command, seq, length, ack, window
    '''
    def __init__(self, commands, seq, length, ack, window, data):
        ''' i believe this is all the possible commands '''
        self.commands = commands
        self.seq = seq
        self.length = length
        self.ack = ack
        self.window = window
        self.data = data
        
    def __str__(self):
        ''' str form for rdp_packets '''
        str_form = ''
        for command in self.commands:
            str_form += command + '|'
        str_form = str_form[:-1] + '\r\n'
        str_form += 'Sequence: ' + str(self.seq) + '\r\n' + 'Length: ' + str(self.length) + '\r\n' + 'Acknowledgement: ' + \
                        str(self.ack) + '\r\n' + 'Window: ' + str(self.window) + '\r\n'
        if self.data:
            str_form += '\r\n' + self.data
        return str_form
    
    def log(self, event):
        ''' print log form to terminal '''
        timestamp = time.strftime('%a %b %d %H:%M:%S ' + 'PDT' + ' %Y: ' ,time.localtime())
        log_form = ''
        for command in self.commands:
            log_form += command + '|'
        log_form = log_form[:-1] + '; '
        log_form += 'Sequence: ' + str(self.seq) + '; ' + 'Length: ' + str(self.length) + '; ' + 'Acknowledgement: ' + \
                        str(self.ack) + '; ' + 'Window: ' + str(self.window)
        print(timestamp + event + '; ' + log_form)
        
        
        
        
class rdp_class:
    ''' handles connection instances '''
    
    def __init__(self):
        
        self.buffer = 0
        self.state = 'close'
        self.keep_alive = False
        # start the instance at closed
        self.current_length = 0
        self.rec = 0
        
    def send_syn(self):
        
        # self, [commands], seq, length, ack, window, data):
        
        rf = read_files.pop(0)
        wf = write_files.pop(0)
        self.current_file = (rf, wf)
        
        self.current_write = open(wf, 'w')
        
        
        if read_files:
            self.keep_alive = True
        else:
            self.keep_alive = False
        
        http_payload = ''
        http_payload += 'GET /' + self.current_file[0] + ' HTTP/1.0\r\n'
        if self.keep_alive == True:
            http_payload += 'Connection: keep-alive\r\n'
        
        
        self.state = 'syn-sent'
        syn_packet = rdp_packet(['SYN', 'DAT', 'ACK'], 0, len(http_payload), -1, client_buffer_size, http_payload)
        snd_buf.put(syn_packet)
        # add log line probably
        
    def rcv_pack(self, packet):
        if 'RST' in packet.commands:
            packet.log('Receive')
            exit()
            
        if 'SYN' in packet.commands:
            self.state == 'syn-rcv'
            # idk why i do this
            self.state == 'connect'
            # now connected to the address
            packet.log('Received')
            
        if 'DAT' in packet.commands:
            write = True
            packet.log('Received')
            data_list = packet.data.split('\r\n\r\n')
            headers = data_list[0].split('\r\n')
            for header in headers:
                if 'HTTP/1.0 404 Not Found' in header:
                    write = False
                
                if 'Content-Length' in header:
                    self.current_length = abs(get_value(header))
                    
            if write == True:
                self.current_write.write(data_list[1])
                self.rec += len(data_list[1])
                self.buffer += packet.length
                
                if self.buffer >= int(client_buffer_size):
                    # need to send ack
                    ack_packet = rdp_packet(['ACK'], packet.ack, 0, packet.seq, client_buffer_size, '')
                    snd_buf.put(ack_packet)
                    self.buffer = 0

                # print(self.rec, self.current_length)
                if self.rec >= self.current_length:
                    # print('get here')

                    self.current_write.close()
                    self.rec = 0
                    self.current_length = 0

                    if self.keep_alive == False:
                        fin_packet = rdp_packet(['FIN', 'ACK'], packet.ack, 0, packet.seq, client_buffer_size, '')
                        snd_buf.put(fin_packet)
                    else:
                        rf = read_files.pop(0)
                        wf = write_files.pop(0)
                        self.current_file = (rf, wf)

                        self.current_write = open(wf, 'w')


                        if read_files:
                            self.keep_alive = True
                        else:
                            self.keep_alive = False

                        http_payload = ''
                        http_payload += 'GET /' + self.current_file[0] + ' HTTP/1.0\r\n'
                        if self.keep_alive == True:
                            http_payload += 'Connection: keep-alive\r\n'

                        syn_packet = rdp_packet(['DAT', 'ACK'], packet.ack + 1, len(http_payload), packet.seq, client_buffer_size, http_payload)
                        snd_buf.put(syn_packet)
                        
            else:

                self.current_write.close()
                self.rec = 0
                self.current_length = 0

                if self.keep_alive == False:
                    fin_packet = rdp_packet(['FIN', 'ACK'], packet.ack, 0, packet.seq, client_buffer_size, '')
                    snd_buf.put(fin_packet)
                else:
                    rf = read_files.pop(0)
                    wf = write_files.pop(0)
                    self.current_file = (rf, wf)

                    self.current_write = open(wf, 'w')


                    if read_files:
                        self.keep_alive = True
                    else:
                        self.keep_alive = False

                    http_payload = ''
                    http_payload += 'GET /' + self.current_file[0] + ' HTTP/1.0\r\n'
                    if self.keep_alive == True:
                        http_payload += 'Connection: keep-alive\r\n'

                    syn_packet = rdp_packet(['DAT', 'ACK'], packet.ack + 1, len(http_payload), packet.seq, client_buffer_size, http_payload)
                    snd_buf.put(syn_packet)

                    
        if 'FIN' in packet.commands:
            packet.log('Received')
            self.state = 'close'
            ack_packet = rdp_packet(['ACK'], packet.ack + 1, 0, packet.seq, client_buffer_size, '')
            snd_buf.put(ack_packet)
                
            

        
        
def get_all_input_files():
    ''' get all the input files from the terminal sys args '''
    i = 5
    rf = sys.argv[i]
    wf = sys.argv[i+1]
    read_files.append(rf)
    write_files.append(wf)
    try:
        while True:
            i += 2
            rf = sys.argv[i]
            wf = sys.argv[i+1]
            read_files.append(rf)
            write_files.append(wf)
    except:
        pass
    finally:
        #print(read_files)
        #print(write_files)
        pass

    
def buffer_to_packet():
    ''' takes the recieving buffer and turns it into packets '''
    try:
        commands = rcv_buf.get_nowait()
        if commands == '':
            commands = rcv_buf.get_nowait()
        seq = rcv_buf.get_nowait()
        length = rcv_buf.get_nowait()
        ack = rcv_buf.get_nowait()
        window = rcv_buf.get_nowait()
        
        commands.replace(" ", "")
        list_of_commands = commands.split('|')
        
        seq_num = get_value(seq)
        length_num = get_value(length)
        ack_num = get_value(ack)
        window_num = get_value(window)
        data = ''
        
        if length_num > 0:
            rcv_buf.get_nowait()
            # remove the one blank line
            
            while True:
                data_line = rcv_buf.get_nowait()
                data += data_line + '\r\n'
                
    except queue.Empty:
        pass
    
    finally:
        if length_num > 0:
            data = data[:-2]
        
        packet = rdp_packet(list_of_commands, seq_num, length_num, ack_num, window_num, data)
        
        # print(packet)
        
        packet_buf.put(packet)
        
        # self, commands, seq, length, ack, window, data


def get_value(string):
    output = ''
    for char in string:
        if char.isdigit() or char == '-':
            output += (char)
    
    return int(output)
        

    
    
get_all_input_files()
        
        
# standard Python boilerplate
if __name__ == '__main__':
    main()
