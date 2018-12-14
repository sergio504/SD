#!/usr/bin/env python3

import socket, sys, os, signal
import szasar
import select
import threading
import time

SERVER_ADD = "localhost"
PORT = 6012
PORT1 = 6013
PORT2 = 6014
PORT_ALT1 = 6016

FILES_PATH = "files"
MAX_FILE_SIZE = 10 * 1 << 20 # 10 MiB
SPACE_MARGIN = 50 * 1 << 20  # 50 MiB
USERS = ("anonymous", "sar", "sza")
PASSWORDS = ("", "sar", "sza")
ALTERNATIVOS = []

class State:
	Identification, Authentication, Main, Downloading, Uploading = range(5)

def sendOK( s, params="" ):
	s.sendall( ("OK{}\r\n".format( params )).encode( "ascii" ) )

def sendER( s, code=1 ):
	s.sendall( ("ER{}\r\n".format( code )).encode( "ascii" ) )


def comprobar():
    #print ("ESTA EN COMPROBAR")
        tiempo1 = time.time()
        while(1):
            tiempo2 = time.time()
            if (tiempo2 - tiempo1 > 5):
                tiempo1 = time.time()
                #empty_socket([dialog_alt])
                print("se va a enviar algo")
                #dialog_alt.sendall("CHECK\r\n".encode("ascii"))
                #preparados, a, e = select.select([dialog_alt], [],[], 5)
                #if (len(preparados) == 0):
                    #print ("HAY UN FALLO EN EL SERVIDOR PRIMARIO")
                #else:
                   # szasar.recvline(dialog_alt).decode("ascii")
                    #print ("Todo va bien")

def empty_socket(sock):
	input = sock
	while 1:
		inputready, o, e = select.select(input, [], [], 0.0)
		if len(inputready) == 0: break
		for s in inputready: s.recv(1)
		break

def comprobarSiOK(dialog_1, dialog_2):
	intentos = 0
	while (1):
		print(intentos)
		intentos = intentos + 1
		disponibles, a, e = select.select([dialog_1, dialog_2], [], [])
		print("DISPONIBLES: " + str(len(disponibles)))
		if (len(disponibles) == 2):
			message_1 = szasar.recvline(dialog_1).decode("ascii")
			message_2 = szasar.recvline(dialog_2).decode("ascii")
			if (message_1[:2] == "OK" and message_2[:2] == "OK"):
				return "OK"
				break
			else:
				return "NO"
				break
		else:
			if (intentos > 10):
				return "NO"
				break




def session( s, s_1, s_2 ):
	global FILES_PATH
	state = State.Identification
	print(s, "\n\n", state)

	while True:
		message = szasar.recvline(dialog).decode("ascii")
		print (message)
		id = message[:4]
		message = message[4:]
		message_r = str(id) + message + "\r\n"
		dialog_1.sendall(message_r.encode("ascii"))
		dialog_2.sendall(message_r.encode("ascii"))
		if not message:
			return

		if message.startswith( szasar.Command.User ):
			empty_socket([dialog_1, dialog_2])
			if( state != State.Identification ):
				sendER( s )
				continue
			try:
				user = USERS.index( message[4:] )
			except:
				sendER( s, 2 )
			else:
				resp = comprobarSiOK(dialog_1, dialog_2)
				if (resp == "OK"):
					state = State.Authentication
					sendOK(s)
				else:
					sendER(s, 12)
					continue

		elif message.startswith( szasar.Command.Password ):
			if state != State.Authentication:
				sendER( s )
				continue
			if( user == 0 or PASSWORDS[user] == message[4:] ):
				resp = comprobarSiOK(dialog_1, dialog_2)
				if (resp == "OK"):
					FILES_PATH = FILES_PATH + "/"+ USERS[user]
					sendOK( s )
					state = State.Main
				else:
					sendER(s, 12)

			else:
				sendER( s, 3 )
				state = State.Identification

		elif message.startswith( szasar.Command.List ):
			if state != State.Main:
				sendER( s )
				continue
			try:
				message = "OK\r\n"
				for filename in os.listdir( FILES_PATH ):
					filesize = os.path.getsize( os.path.join( FILES_PATH, filename ) )
					message += "{}?{}\r\n".format( filename, filesize )
				message += "\r\n"
			except:
				sendER( s, 4 )
			else:
				resp = comprobarSiOK(dialog_1, dialog_2)
				if (resp == "OK"):
					s.sendall(message.encode("ascii"))
				else:
					sendER(s, 12)
					continue

		elif message.startswith( szasar.Command.Download ):
			if state != State.Main:
				sendER( s )
				continue
			filename = os.path.join( FILES_PATH, message[4:] )
			try:
				filesize = os.path.getsize( filename )
			except:
				sendER( s, 5 )
				continue
			else:
				resp = comprobarSiOK(dialog_1, dialog_2)
				if (resp == "OK"):
					sendOK(s, filesize)
					state = State.Downloading
				else:
					sendER(s, 12)
					continue

		elif message.startswith( szasar.Command.Download2 ):
			if state != State.Downloading:
				sendER( s )
				continue
			state = State.Main
			try:
				with open( filename, "rb" ) as f:
					filedata = f.read()
			except:
				sendER( s, 6 )
			else:
				resp = comprobarSiOK(dialog_1, dialog_2)
				if (resp == "OK"):
					sendOK(s)
					s.sendall(filedata)

				else:
					sendER(s, 12)
					continue


		elif message.startswith( szasar.Command.Upload ):
			if state != State.Main:
				sendER( s )
				continue
			if user == 0:
				sendER( s, 7 )
				continue
			filename, filesize = message[4:].split('?')
			filesize = int(filesize)
			if filesize > MAX_FILE_SIZE:
				sendER( s, 8 )
				continue
			svfs = os.statvfs( FILES_PATH )
			if filesize + SPACE_MARGIN > svfs.f_bsize * svfs.f_bavail:
				sendER( s, 9 )
				continue
			resp = comprobarSiOK(dialog_1, dialog_2)
			if (resp == "OK"):
				sendOK(s)
				state = State.Uploading
			else:
				sendER(s, 12)
				continue


		elif message.startswith( szasar.Command.Upload2 ):
			if state != State.Uploading:
				sendER( s )
				continue
			state = State.Main
			try:
				with open( os.path.join( FILES_PATH, filename), "wb" ) as f:
					filedata = szasar.recvall( s, filesize )
					f.write( filedata )
			except:
				sendER( s, 10 )
			else:
				resp = comprobarSiOK(dialog_1, dialog_2)
				if (resp == "OK"):
					sendOK(s)
				else:
					sendER(s, 12)
					continue


		elif message.startswith( szasar.Command.Delete ):
			if state != State.Main:
				sendER( s )
				continue
			if user == 0:
				sendER( s, 7 )
				continue
			try:
				os.remove( os.path.join( FILES_PATH, message[4:] ) )
			except:
				sendER( s, 11 )
			else:
				resp = comprobarSiOK(dialog_1, dialog_2)
				if (resp == "OK"):
					sendOK(s)
					s.sendall(filedata)

				else:
					sendER(s, 12)
					continue


		elif message.startswith( szasar.Command.Exit ):
			sendOK( s )
			return

		else:
			sendER( s )






if __name__ == "__main__":

	if (0):
		print ("Da true con 0. creo esto")
	else:
		print ("DA true con cualquier numero.")


	s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
	s.bind(('', PORT))
	s.listen( 5 )

	signal.signal(signal.SIGCHLD, signal.SIG_IGN)

	sock_r1=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	sock_r1.bind(('', PORT1))
	sock_r1.listen(5)

	sock_r1_alt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock_r1_alt.bind(('', PORT_ALT1))
	sock_r1_alt.listen(5)

	sock_r2=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	sock_r2.bind(('', PORT2))
	sock_r2.listen(5)






	while True:
		dialog, address = s.accept()
		dialog_1, addres_1 = sock_r1.accept()
		dialog_alt1, _ = sock_r1_alt.accept()

		ALTERNATIVOS.append(dialog_alt1)

		dialog_2, addres_2 = sock_r2.accept()


		if( os.fork() ):
			dialog.close()
			dialog_2.close()
			dialog_1.close()

		else:
			s.close()
			sock_r1.close()
			sock_r2.close()


			t = threading.Thread(target=comprobar())
			t.start()
			print("AQUI")


			
			session( dialog, dialog_1, dialog_2)




			dialog.close()
			dialog_1.close()
			dialog_2.close()
	exit( 0 )
