#!/usr/bin/env python3

import socket, sys, os, signal
import szasar
import select

PORT2 = 6014
FILES_PATH = "files2"
MAX_FILE_SIZE = 10 * 1 << 20  # 10 MiB
SPACE_MARGIN = 50 * 1 << 20  # 50 MiB
USERS = ("anonymous", "sar", "sza")
PASSWORDS = ("", "sar", "sza")
SERVER = 'localhost'
PORT_R = 6015
PORT_ALT = 6017
user = ""
filename = ""
filesize = 0


def comprobar(s_alt):
    while (1):
        preparados, _, _ = select.select([s_alt], [], [], 10)
        if (len(preparados) == 0):
            print ("HA FALLADO EL SERVIDOR PRIMARIO")
        else:
            szasar.recvline(s_alt).decode("ascii")
            s_alt.sendall("OK\r\n".encode("ascii"))


def empty_socket(sock):
	input = sock
	while 1:
		inputready, o, e = select.select(input, [], [], 0.0)
		if len(inputready) == 0: break
		for s in inputready: s.recv(1)
		break


class State:
    Identification, Authentication, Main, Downloading, Uploading = range(5)

state = State.Identification

def sendOK(s, params=""):
    s.sendall(("OK{}\r\n".format(params)).encode("ascii"))


def sendER(s, code=1):
    s.sendall(("ER{}\r\n".format(code)).encode("ascii"))

def tratarMensaje(message,s):
    print ("tratado: "+ message)
    global FILES_PATH
    global user
    global filename
    global filesize
    global state

    if message.startswith(szasar.Command.User):
        if (state != State.Identification):
            sendER(s)
        try:
            user = USERS.index(message[4:])
        except:
            sendER(s, 2)
        else:
            sendOK(s)
            state = State.Authentication

    elif message.startswith(szasar.Command.Password):
        if state != State.Authentication:
            sendER(s)
        if ( user == 0 or PASSWORDS[user] == message[4:]):
            FILES_PATH = FILES_PATH + "/" + USERS[user]

            sendOK(s)
            state = State.Main

        else:
            sendER(s, 3)
            state = State.Identification

    elif message.startswith(szasar.Command.List):
        if state != State.Main:
            sendER(s)
        try:
            message = "OK\r\n"
            for filename in os.listdir(FILES_PATH):
                filesize = os.path.getsize(os.path.join(FILES_PATH, filename))
                message += "{}?{}\r\n".format(filename, filesize)
            message += "\r\n"
        except:
            sendER(s, 4)
        else:
            s.sendall(message.encode("ascii"))

    elif message.startswith(szasar.Command.Download):
        if state != State.Main:
            sendER
        filename = os.path.join(FILES_PATH, message[4:])
        try:
            filesize = os.path.getsize(filename)
        except:
            sendER(s, 5)
        else:
            sendOK(s, filesize)
            state = State.Downloading

    elif message.startswith(szasar.Command.Download2):
        if state != State.Downloading:
            sendER(s)
        state = State.Main
        try:
            with open(filename, "rb") as f:
                filedata = f.read()
        except:
            sendER(s, 6)
        else:
            sendOK(s)
            s.sendall(filedata)

    elif message.startswith(szasar.Command.Upload):
        if state != State.Main:
            sendER(s)
        if user == 0:
            sendER(s, 7)
        filename, filesize = message[4:].split('?')
        filesize = int(filesize)
        if filesize > MAX_FILE_SIZE:
            sendER(s, 8)
        svfs = os.statvfs(FILES_PATH)
        if filesize + SPACE_MARGIN > svfs.f_bsize * svfs.f_bavail:
            sendER(s, 9)
        sendOK(s)
        state = State.Uploading

    elif message.startswith(szasar.Command.Upload2):
        if state != State.Uploading:
            sendER(s)
        state = State.Main
        try:
            with open(os.path.join(FILES_PATH, filename), "wb") as f:
                filedata = szasar.recvall(s, filesize)
                f.write(filedata)
        except:
            sendER(s, 10)
        else:
            sendOK(s)

    elif message.startswith(szasar.Command.Delete):
        if state != State.Main:
            sendER(s)

        if user == 0:
            sendER(s, 7)

        try:
            os.remove(os.path.join(FILES_PATH, message[4:]))
        except:
            sendER(s, 11)
        else:
            sendOK(s)

    elif message.startswith(szasar.Command.Exit):
        sendOK(s)
        return

    else:
        sendER(s)



def difundir(message, sr):
    message_r = message + "\r\n"
    sr.sendall(message_r.encode("ascii"))

def session(s, sr):
    ULTIMO = 0
    inputs = [s, sr]
    while True:
        disponibles = 0
        while disponibles == 0:
            inready, outready, excready = select.select(inputs, [], [])
            disponibles = len(inready)
            print ("SOCKETS CON MENSAJE " + str(disponibles))


        if (disponibles == 1):
            if (s in inready):
                print ("MENSAJE DE S")
                message = szasar.recvline(s).decode("ascii")
                print (message)
                if (int(message[:4]) > int(ULTIMO)):
                    ULTIMO = message[:4]
                    difundir(message, sr)
                    tratarMensaje(message[4:], s)
            elif (sr in inready):
                print("MENSAJE DE SR")
                message = szasar.recvline(sr).decode("ascii")
                print(message)
                if (int(message[:4]) > int(ULTIMO)):
                    ULTIMO = message[:4]
                    tratarMensaje(message[4:], s)

        elif (disponibles == 2):
            print ("ESTAN LOS DOS")
            message_s = szasar.recvline(s).decode()
            message_r = szasar.recvline(sr).decode()
            ID_s = message_s[:4]
            ID_r = message_r[:4]
            if (int(ID_s) > int(ULTIMO)):
                ULTIMO = message_s[:4]
                difundir(message_s, sr)
                tratarMensaje(message_s[4:], s)
            if (int(ID_r) > int(ULTIMO)):
                ULTIMO = message_r[:4]
                tratarMensaje(message_r[4:], s)


if __name__ == "__main__":
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER, PORT2))

    sr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sr.connect((SERVER, PORT_R))


    session(s, sr)

