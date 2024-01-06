import socket
import select
import sys
import queue
import time
import re
import typing
import os.path

inputs = []
outputs = []
server = None

message_queues = {}
response_messages = {}
# outgoing message queues

keep_server_alive = {}
address_info = {}
request_message = {}
# request message

def main():
    
    ip_address = sys.argv[1]
    port_number = int(sys.argv[2])
    server_address = (ip_address, port_number)
    # setup of server address based off of input
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(server_address)
    # set up TCP, setblocking, and bind...

    server.listen(5)
    inputs.append(server)
    # listen and append server to inputs
    
    while True:
        # wait for one socket to be ready
        readable, writable, exceptional = select.select(inputs, outputs, inputs)

        for sock in readable:
        
            if sock is server:
                handle_new_connection(sock)
                # if s is a server add the connection
            else:
                handle_existing_connection(sock)
                
           
        for sock in writable:
            write_back_response(sock)
        
        for sock in exceptional:
            handle_connection_error(sock)
                    
                
                                                        
def get_timestamp():
    ''' get_timestamp Function
    Returns the formatted current time with abbreviated timezone
    '''
    current_time = time.localtime()
    # get current time
    timezone = time.strftime("%Z" ,current_time)
    timezone = re.sub(r'[a-z]', '', timezone)
    timezone = re.sub(r' ', '', timezone)
    # get abbreviated timezone
    timestamp = time.strftime("%a %b %d %H:%M:%S " + timezone + " %Y:" ,current_time)
    return timestamp


def get_log(sock, response_message, req_msg):
    ''' get_log Function
    returns a properly formatted log for sws to print
    '''
    output_log = ""
    c_address = " " + address_info[sock][0] + ":" + str(address_info[sock][1])
    output_log += get_timestamp() + c_address + " " + req_msg + "; " + re.sub(r"\n", "", response_message)
    
    return output_log


def send_file_if_exists(sock, filename):
    ''' send_file_if_exists Function
    sends the file through the socket if file is able to open
    '''
    
    if not (filename == ""):
        try:
            with open(filename) as file:
                lines = file.readlines()
            
            sock.send("\n\r\n\r".encode('utf-8'))
            for line in lines:
                sock.send(line.encode('utf-8'))
                
            sock.send('\n\n\n'.encode('utf-8'))
            # newline
        except:
            nofile = 0


def check_multiple_requests(message):
    ''' check_multiple_requests Function
    checks if multiple requests (via pipe text file)
    '''
    
    if (message.count("\n\n") > 1) or (message.count("\r\n\r\n") > 1):
        return True
    else:
        return False
    

def split_multiple_requests(message):
    ''' split_multiple_requests Function
    splits the multi request message into single commands
    returns a list of commands
    '''
    
    if "\r\n\r\n" in message:
        output = message.split("\r\n\r\n")
        for req_message in output:
            req_message = req_message + "\r\n\r\n"
    else:
        output = message.split("\n\n")
        for req_message in output:
            req_message = req_message + "\n\n"

    return output

    
    
def check_message(message):
    ''' check_message Function
    checks whether a message is formatted correctly and has keep alive
    '''
    
    get_good = False
    connection_good = False
    keep_alive = False
    
    formatted_lines = []
    message_lines = message.split("\n")

    for line in message_lines:
        current_line = line
        current_line = re.sub(r'\r', '', current_line)
        current_line = re.sub(r'\n', '', current_line)
        formatted_lines.append(current_line)
        # this removes all the newlines/returns and adds lines to new list

    
    try:
        if formatted_lines[0].startswith('GET /') and formatted_lines[0].endswith(' HTTP/1.0'):
            get_good = True
            # first header is good
        else:
            get_good = False
    except:
        return False, False
        # since format cannot be right since no input
    
    try:
        keep_alive_lower = formatted_lines[1].lower()
        lower_list = keep_alive_lower.split(":")
        if (lower_list[0] == "connection") and (lower_list[1].strip() == "keep-alive"):
            connection_good = True
            keep_alive = True
        elif (lower_list[0] == "connection") and (lower_list[1].strip() == "close"):
            connection_good = True
            keep_alive = False
        elif (keep_alive_lower == ''):
            connection_good = True
            keep_alive = False
        else:
            connection_good = True
            keep_alive = False
    except:
        return False, False
    
    return (connection_good and get_good), keep_alive


    
def message_finished(message):
    ''' messageNotFinished Function
    allows for a message to accumulate until it ends
    with either \r\n\r\n or \n\n
    '''
    if message.endswith("\r\n\r\n") or message.endswith("\n\n"):
        return True
    else:
        return False

    
def kept_alive(sock):
    ''' kept_alive function
    function to check if socket was kept alive
    '''
    try:
        return keep_server_alive[sock]
    except:
        return False

def find_file_from_message(message):
    ''' find_file_from_message Function
    filters the CORRECTLY FORMATTED http request to find the filename
    '''
    message_lines = message.splitlines()
    req_line = message_lines[0]
    req_lines = req_line.split("/")
    filename = re.sub(r" HTTP", "", req_lines[1])
    
    return filename
    
    
    
def handle_response_message(message):
    '''handle_response_message Function
    logically handles whether a message is valid or not
    
    returns (in order): servers response, keep alive status, filename
    '''
    bad_request = "HTTP/1.0 400 Bad Request\r\n"
    file_incorrect = "HTTP/1.0 404 Not Found\r\n"
    good_request = "HTTP/1.0 200 OK\r\n"
    filename = ""
    
    format_status, keep_alive = check_message(message)
    
    if format_status:
        
        filename = find_file_from_message(message)
        
        if os.path.isfile(filename):
            return good_request, keep_alive, filename
            # if the file exists
        else:
            return file_incorrect, keep_alive, filename
            # file does not exist 404 error
    else:
        return bad_request, False, ""

    
    
def handle_new_connection(sock):
    ''' handle_new_connection Function
    adds a connection to list of inputs, sets up socket for reading
    '''
    connection, address = sock.accept()
    inputs.append(connection)
    address_info[connection] = (address[0], address[1])
    message_queues[connection] = queue.Queue()
    
    
def handle_existing_connection(sock):
    ''' handle_existing_connection Function
    reads message(s), and sets up response message(s) via helper functions
    '''
    message = sock.recv(1024).decode()
    
    if message:
        try:
            request_message[sock] = request_message[sock] + message
        except:
            request_message[sock] = message
                
        if message_finished(request_message[sock]):
            whole_message = request_message[sock]
            
            outputs.append(sock)
            
            # multiple request handler
            if check_multiple_requests(whole_message):
                
                multi_req = split_multiple_requests(whole_message)
                one_more = False
                
                for req in multi_req:
                    response_msg, keep_alive, filename = handle_response_message(req)
                    
                    req_msg = re.sub(r"\n", "", req)
                    req_msg = re.sub(r"Connection", " Connection", req_msg)
                    
                    req_msg_list = req_msg.split("HTTP/1.0")
                    req_msg = req_msg_list[0] + "HTTP/1.0"
                    
                    if (keep_alive == True):
                        req_msg = req_msg + " Connection: Keep-alive"
                    
                    keep_server_alive[sock] = keep_alive
                    if keep_alive:
                        message_queues[sock].put([response_msg, req_msg, filename])
                    elif (keep_alive == False) and (one_more == False):
                        message_queues[sock].put([response_msg, req_msg, filename])
                        one_more = True
                    # keeps track of filename, keep_alive status and puts msg into queue
                
            # single request in terminal
            else:
                req_msg = re.sub(r"\n", "", whole_message)
                req_msg = re.sub(r"Connection", " Connection", req_msg)
                
                request_message[sock] = ""
                
                response_msg, keep_alive, filename = handle_response_message(whole_message)
                
                req_msg_list = req_msg.split("HTTP/1.0")
                req_msg = req_msg_list[0] + "HTTP/1.0"
                
                if (keep_alive == True):
                    req_msg = req_msg + " Connection: Keep-alive"
            
                keep_server_alive[sock] = keep_alive
                message_queues[sock].put([response_msg, req_msg, filename])
                # keeps track of filename, keep_alive status and puts msg into queue

    else:
        close_connection(sock)
        # this closes the connection if no message


        
def close_connection(sock):
    ''' close_connection Function
    close connection via sock id
    '''
    
    if sock in outputs:
        outputs.remove(sock)
    inputs.remove(sock)
    sock.close()
    
    del message_queues[sock]
    
            
            
def write_back_response(sock):
    ''' write_back_response Function
    outputs responses to appropriate client, using queues
    '''

    try:
        next_message = (message_queues[sock].get_nowait())
        # next_message contains a tuple with (response, request)
    except queue.Empty:
        # this means the queue is empty so output is finished
        outputs.remove(sock)
        # need to remove sock from writable since no more responses
        
        if not kept_alive(sock):
            inputs.remove(sock)
            sock.close()
        # if response queue is empty 
    else:
        print_msg = get_log(sock, next_message[0], next_message[1])
        if kept_alive(sock):
            encoded_message = ("\n" + next_message[0] + "Connection: Keep-alive\r\n\r\n").encode('utf-8')
        else:
            encoded_message = ("\n" + next_message[0]).encode('utf-8')
        
        sock.send(encoded_message)
        send_file_if_exists(sock, next_message[2])
        print(print_msg)
         

            
def handle_connection_error(sock):
    close_connection(sock)

         
# standard Python boilerplate
if __name__ == '__main__':
    main()                
        
            