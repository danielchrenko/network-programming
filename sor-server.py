import socket
import select
import sys
import queue
import time
import re
import os

# input: 
# python3 sor-server.py server_ip_address server_udp_port_number server_buffer_size server_payload_length
# python3 sor-server.py 10.10.1.100 8888 5120 1024
# server buffer and payload both 1000 for now

total_sent = {}
sending_buffer = {}
receiving_buffer = {}
packet_buffer = {}
state = {}
window = {}
file = {}
read_handle = {}
seq = {}
length = {}
ack = {}
# message queues (need to be global)

snd_buf = queue.Queue()


def main():

    ip_address = sys.argv[1]
    port_number = int(sys.argv[2])
    server_address = (ip_address, port_number)

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(server_address)
    # initialization
    
    while True:

        readable, writable, exceptional = select.select([udp_sock], [udp_sock], [udp_sock])

        if udp_sock in readable:
            
            message, addr = udp_sock.recvfrom(2048)
            full_message = message.decode()
            lines = full_message.split('\r\n')
            
            if not addr in receiving_buffer.keys():
                receiving_buffer[addr] = queue.Queue()
                sending_buffer[addr] = queue.Queue()
                state[addr] = 'close'
            
            for line in lines:
                receiving_buffer[addr].put(line)
                
            buffer_to_packet(addr)
            # this puts all the rec buffer and puts into packets
            
            try:
                while packet_buffer[addr]:
                    packet = packet_buffer[addr].get_nowait()
                    
                    #  print(packet)
                    
                    if ('SYN' in packet.commands) and (packet.length > int(sys.argv[3])):
                        # SEND RST PACKET IF INVALID RQSIZE
                        rst(udp_sock, addr)
                        break
                        
                    handle_packet(packet, addr)

            except queue.Empty:
                pass
            
        
            
        if udp_sock in writable:
            
            for key in sending_buffer:
                
                try:
                    packet = sending_buffer[key].get_nowait()
                    # print(packet)
                    packet_message = str(packet).encode()
                    bytes_sent = udp_sock.sendto(packet_message, key)
                    # packet.log('Send')
                except queue.Empty:
                    pass
                    # basically output anything that is anywhere in queue, using keys that hsa the address to mail to
            



class rdp_class:
    ''' rdp class im not sure, this will be the state machine '''
    
    def __init__(self):
        self.state = 'close'
        self.keep_alive = False
        # start the instance at closed

        
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

        
        
def clear_buffers(addr):
    ''' clears all the buffers for the addr '''
    del sending_buffer[addr]
    del receiving_buffer[addr]
    del state[addr]
        
        
        
def rst(udp_sock, addr):
    ''' clear buffers for the addr and send out an rst packet '''
    buffer = int(sys.argv[3])
    clear_buffers(addr)
    packet = rdp_packet(['RST'], 0, 0, -1, buffer, '')
    packet_message = str(packet).encode()
    udp_sock.sendto(packet_message, addr)
    
    
    
        
        
def get_file(data):
    ''' use the sws stuff '''
    keep_alive = False
    data_lines = data.split('\r\n')
    get_line = data_lines[0]
    get_line = get_line.replace("GET /", "")
    request_file = get_line.replace(" HTTP/1.0", "")
    # print(request_file)
    
    try:
        if data_lines[1].lower() == 'connection: keep-alive':
            keep_alive = True
    except:
        keep_alive = False
        
    return request_file
        
        
def handle_packet(packet, addr):
    ''' handles the packet and state machine '''
    
    buffer = int(sys.argv[3])
    packet_length = int(sys.argv[4])
    
    if 'DAT' in packet.commands and state[addr] == 'close':
        
        state[addr] = 'open'
        ack[addr] = 0
        length[addr] = packet.length
        seq[addr] = 0
        window[addr] = 0
        file[addr] = ''
        total_sent[addr] = 0
        
        # print('recieved syn, changing state to syn-rcv')
        # need to create a packet to ack the syn
        file[addr] = get_file(packet.data)
        # needs to be before in order to get right packet
        syn_packet = rdp_packet(['SYN', 'ACK'], 0, 0, 1, buffer, '')
        ack[addr] += 1 + packet.length
        sending_buffer[addr].put(syn_packet) 
        # print('put packet onto sending buffer for', addr)
        
        if os.path.exists(file[addr]):
            timestamp = time.strftime('%a %b %d %H:%M:%S ' + 'PDT' + ' %Y: ' ,time.localtime())
            req = timestamp + addr[0] + ":" + str(addr[1]) + " GET /" + file[addr] + " HTTP/1.0; HTTP/1.0 200 OK"
            print(req)
            read_handle[addr] = open(file[addr], 'r')
            http_response = "HTTP/1.0 200 OK\r\nContent-Length: " + str(os.path.getsize(file[addr])) + "\r\n\r\n"
            
            # print(buffer, total_sent[addr], os.path.getsize(file[addr]))
            while window[addr] < packet.window and total_sent[addr] < os.path.getsize(file[addr]):
                left = os.path.getsize(file[addr]) - total_sent[addr]

                if left < packet_length:
                    # use left length as next length and break
                    data = read_handle[addr].read(left)
                    dat_packet = rdp_packet(['DAT', 'ACK'], seq[addr], left, ack[addr], buffer, http_response + data)
                    total_sent[addr] += left
                    window[addr] += left
                    seq[addr] += left
                    sending_buffer[addr].put(dat_packet)
                    break
                else:
                    data = read_handle[addr].read(packet_length)
                    dat_packet = rdp_packet(['DAT', 'ACK'], seq[addr], packet_length, ack[addr], buffer, http_response + data)
                    total_sent[addr] += packet_length
                    window[addr] += packet_length
                    seq[addr] += packet_length
                    sending_buffer[addr].put(dat_packet)
        else:
            http_response = "HTTP/1.0 404 Not Found\r\n"
            timestamp = time.strftime('%a %b %d %H:%M:%S ' + 'PDT' + ' %Y: ' ,time.localtime())
            req = timestamp + addr[0] + ":" + str(addr[1]) + " GET /" + file[addr] + " HTTP/1.0; HTTP/1.0 404 Not Found"
            dat_packet = rdp_packet(['DAT', 'ACK'], seq[addr], len(http_response), ack[addr], buffer, http_response)
            sending_buffer[addr].put(dat_packet)
        
                
    elif 'DAT' in packet.commands:
        
        window[addr] = 0
        total_sent[addr] = 0
        # print('recieved syn, changing state to syn-rcv')
        # need to create a packet to ack the syn
        file[addr] = get_file(packet.data)
        # print(file[addr])
        # needs to be before in order to get right packet
        # syn_packet = rdp_packet(['SYN', 'ACK'], 0, 0, 1, buffer, '')
        ack[addr] += 1 + packet.length
        # sending_buffer[addr].put(syn_packet) 
        # print('put packet onto sending buffer for', addr)
        
        if os.path.exists(file[addr]):
            timestamp = time.strftime('%a %b %d %H:%M:%S ' + 'PDT' + ' %Y: ' ,time.localtime())
            req = timestamp + addr[0] + ":" + str(addr[1]) + " GET /" + file[addr] + " HTTP/1.0; HTTP/1.0 200 OK"
            print(req)
            read_handle[addr] = open(file[addr], 'r')
            http_response = "HTTP/1.0 200 OK\r\nContent-Length: " + str(os.path.getsize(file[addr])) + "\r\n\r\n"
            
            while window[addr] < packet.window and total_sent[addr] < os.path.getsize(file[addr]):
                left = os.path.getsize(file[addr]) - total_sent[addr]
                if left < packet_length:
                    # use left length as next length and break
                    data = read_handle[addr].read(left)
                    dat_packet = rdp_packet(['DAT', 'ACK'], seq[addr], left, ack[addr], buffer, http_response + data)
                    total_sent[addr] += left
                    window[addr] += left
                    seq[addr] += left
                    sending_buffer[addr].put(dat_packet)
                    break
                else:
                    data = read_handle[addr].read(packet_length)
                    dat_packet = rdp_packet(['DAT', 'ACK'], seq[addr], packet_length, ack[addr], buffer, http_response + data)
                    total_sent[addr] += packet_length
                    window[addr] += packet_length
                    seq[addr] += packet_length
                    sending_buffer[addr].put(dat_packet)
        else:
            http_response = "HTTP/1.0 404 Not Found\r\n"
            timestamp = time.strftime('%a %b %d %H:%M:%S ' + 'PDT' + ' %Y: ' ,time.localtime())
            req = timestamp + addr[0] + ":" + str(addr[1]) + " GET /" + file[addr] + " HTTP/1.0; HTTP/1.0 404 Not Found"
            print(req)
            dat_packet = rdp_packet(['DAT', 'ACK'], seq[addr], len(http_response), ack[addr], buffer, http_response)
            sending_buffer[addr].put(dat_packet)
        
        
                
    elif 'ACK' in packet.commands and len(packet.commands) == 1:
        
        if not state[addr] == 'fin-sent':
        
            window[addr] = 0
            http_response = "HTTP/1.0 200 OK\r\nContent-Length: " + str(os.path.getsize(file[addr])) + "\r\n\r\n"

            while window[addr] < packet.window and total_sent[addr] < os.path.getsize(file[addr]):
                left = os.path.getsize(file[addr]) - total_sent[addr]

                if left < packet_length:
                    # use left length as next length and break
                    data = read_handle[addr].read(left)
                    dat_packet = rdp_packet(['DAT', 'ACK'], seq[addr], left, ack[addr], buffer, http_response + data)
                    total_sent[addr] += left
                    window[addr] += left
                    seq[addr] += left
                    sending_buffer[addr].put(dat_packet)
                    break
                else:
                    data = read_handle[addr].read(packet_length)
                    dat_packet = rdp_packet(['DAT', 'ACK'], seq[addr], packet_length, ack[addr], buffer, http_response + data)
                    total_sent[addr] += packet_length
                    window[addr] += packet_length
                    seq[addr] += packet_length
                    sending_buffer[addr].put(dat_packet)
                    
        else:
            state[addr] = 'close'
                
    elif 'FIN' in packet.commands:
        
        state[addr] = 'fin-sent'
        fin_packet = rdp_packet(['FIN', 'ACK'], seq[addr], 0, ack[addr], buffer, '')
        sending_buffer[addr].put(fin_packet) 
        
            
            
    
        

        
def buffer_to_packet(addr):
    ''' takes the recieving buffer and turns it into packets '''
    try:
        commands = receiving_buffer[addr].get_nowait()
        if commands == "":
            commands = receiving_buffer[addr].get_nowait()
        seq = receiving_buffer[addr].get_nowait()
        length = receiving_buffer[addr].get_nowait()
        ack = receiving_buffer[addr].get_nowait()
        window = receiving_buffer[addr].get_nowait()
        
        commands.replace(" ", "")
        list_of_commands = commands.split('|')
        
        seq_num = get_value(seq)
        length_num = get_value(length)
        ack_num = get_value(ack)
        window_num = get_value(window)
        data = ''
        
        if length_num > 0:
            receiving_buffer[addr].get_nowait()
            # remove the one blank line
            
            while True:
                data_line = receiving_buffer[addr].get_nowait()
                data += data_line + '\r\n'
                
    except queue.Empty:
        pass
    
    finally:
        if length_num > 0:
            data = data[:-2]
        
        if not addr in packet_buffer:
            packet_buffer[addr] = queue.Queue()
        
        packet = rdp_packet(list_of_commands, seq_num, length_num, ack_num, window_num, data)
        packet_buffer[addr].put(packet)
        
        # self, commands, seq, length, ack, window, data
        

def get_value(string):
    output = ''
    for char in string:
        if char.isdigit() or char == '-':
            output += (char)
    
    return int(output)
        
        
# standard Python boilerplate
if __name__ == '__main__':
    main()
