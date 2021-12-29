#__________________________IMPORT LIBRARIES AND FILES____________________________________________________________________________
import sys,requests,hashlib,bencodepy,random
import socket
from urllib.parse import urlparse
from struct import *
from _thread import *
from threading import *
from msg_format import msg_udp_tr, msg_peer_comm
from display import display
from settings import run
import logging
import math
import time
import decoding
import string
import os

 
#_____________________________PART 1 : Program Variables & Decoding Torrent:_____________________________________________________
# Torrent parameters : max download speed & loc / max upload speed & loc / Downloaded pieces / Max peers
torrent_parameters={
	"maxm_speed_download": 0,
	"maxm_speed_upload": 0,
	"pieces_downloaded": 0,
	"download_location":os.getcwd()+"/",
	"upload_location":"",
	"maxm_peers":50
}

start_app = run()
torrent_parameters = start_app.start(torrent_parameters)

f = open(sys.argv[1] , "rb")
decd_data = bencodepy.decode(f.read())

dict_metadata = {}
for key, val in decd_data.items():
	dict_metadata[key.decode()] = val	

metadata = decoding.torrent_file_decode(sys.argv[1])
sha1_info = hashlib.sha1(bencodepy.encode(dict_metadata['info'])).digest()

# Random generated peer id for user
PEER_ID = ''.join(random.choices(string.digits, k=20))

# Port number user is going to listen on for request from other peers
PORT_NO = 6881

# Peer Parameters : Info hash, peer id, uploaded, downloaded, left/incomplete, port number
peer_parameters = {
	"info_hash": sha1_info,
	"peer_id" : PEER_ID,
	"uploaded" : 0,
	"downloaded" : 0,
	"left":metadata['info']['length'],
	"port":PORT_NO
}

# Piece Parameters : index, done, downloading, offset, downloading peer, available, count
piece_parameters = [{"index": i, 
			"done" : False, 
			"downloading" : False, 
			"offset": 0 , 
			"downloading_peer": None, 
			"available": 0, 
			"count": 0 } 
			for i in range(0,len(metadata['info']['pieces']))]

# Sorted List of rarest pieces
list_rarest = []

# Open torrent file
try:
	file_download = open(torrent_parameters['download_location']+metadata['info']['name'],"rb+")	
except:
	make_file = open(torrent_parameters['download_location']+metadata['info']['name'],"w")
	make_file.close()
	file_download = open(torrent_parameters['download_location']+metadata['info']['name'],"rb+")

# List of all peers returned by the tracker
list_peers = []

# Locks are threading functions used to maintain a fixed state of thread while updating variables initialized globally
# 1. Lock for received pieces list
lock_piece = Lock() 
# 2. Lock for rarest piece list
lock_rarest = Lock() 
# 3. Lock for peers list
lock_peer = Lock()	

#_____________________________PART 2 : Get Peers From Trackers:___________________________________________________________
# Function extracts and returns peers from http trackers
def http_scraper(url, peer_parameters):
	global list_peers
	try:
		response = requests.get(url, params = peer_parameters, timeout = 10)
		if(response):
			temp,details_peer = {}, bencodepy.decode(response.content)	
			for key, val in details_peer.items():
				temp[key.decode()] = val
			details_peer = temp	
			for peer in details_peer['peers']:
				temp = {}
				for key, val in peer.items():
					temp[key.decode()] = val		
				del temp['peer id']
				temp['ip'] = temp['ip'].decode()
				lock_peer.acquire()
				list_peers.append(temp)
				lock_peer.release()		
	except Exception as e:
		return None	
	
# Function extracts and returns peers from udp trackers
def udp_scraper(domain, port, peer_parameters):
	global list_peers
	# Connection Request and Response
	
	u = msg_udp_tr()
	data = u.msg_conn()
	n = 0
	
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.settimeout(10)
	try:
		sock.sendto(data,(domain,int(port)))
	except Exception as e:
		return None	
	try:
		data, server = sock.recvfrom(1024)
		action,transaction_id,connection_id = unpack('!iiq',data)	
	except:
		return None

	# IPV4 Announce Request         
	#action  = 1 # Action for Announce 
	
	data = u.ipv4_annouce_req(peer_parameters,connection_id)
	
	try:
		sock.sendto(data,(domain,int(port)))
	except Exception as e:
		return None

	# IPV4 Announce Response	    	
	try:
		data, server = sock.recvfrom(1024)
		if(len(data) >= 20):			
			response = u.ipv4_announce_res(data)
			lock_peer.acquire()
			for x in range(0,len(response),5):
				ip1,ip2,ip3,ip4,port = response[x:x+5]
				ip = str(ip1)+"."+str(ip2)+"."+str(ip3)+"."+str(ip4)
				list_peers.append({'ip':ip, 'port':port})
			lock_peer.release()		
	except Exception as e:
		return None		
	
# Function get all peers from trackers (apply max list_peers setting)
def get_peers_from_trackers(metadata, peer_parameters):
	url_p = urlparse(metadata['announce'])
	global list_peers
	http_threads = []
	udp_threads = []
	temp = []
	if(url_p.scheme == 'http' or url_p.scheme == 'https'):
		http_threads.append(Thread(target = http_scraper,args = (metadata['announce'],peer_parameters)))	
	elif(url_p.scheme == 'udp'):
		domain, port = url_p.netloc.split(":")
		udp_threads.append(Thread(target = udp_scraper, args = (domain,port,peer_parameters)))
		
	for tracker in metadata['announce-list']:
		url_p = urlparse(tracker[0])
		if(url_p.scheme == 'udp'):
			domain, port = url_p.netloc.split(":")
			udp_threads.append(Thread(target = udp_scraper, args = (domain,port,peer_parameters)))	
		elif(url_p.scheme == 'https' or url_p.scheme == 'http'):
			http_threads.append(Thread(target = http_scraper,args = (tracker[0], peer_parameters)))

	for thread in http_threads:
		thread.start()
	for thread in udp_threads:
		thread.start()
	for thread in http_threads:
		thread.join()
	for thread in udp_threads:
		thread.join()		
	for peer in list_peers:
		if peer not in temp:
			if len(temp) <= torrent_parameters['maxm_peers']:
				temp.append(peer)
	list_peers = temp	

#_____________________________PART 3 : Peer and Piece Management & Communication:____________________________________________________
# Function handles the peer communication to collect all pieces
# State meanings: 0 = No Handshake, 1 = Handshake Done, 2 = Bitfield Received, 3 = Peer is Unchoked

def peer_handler(ip, port, peer_parameters, peer_index, torrent_parameters):
	global list_rarest
	mpc = msg_peer_comm()
	peer_id = b''
	if type(ip) is bytes:
		ip = ip.decode()
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.settimeout(30)
	try:
		sock.connect((ip,port))
	except Exception as e:
		return
	try:
		state = 0
		alive = 1
		bitfield = b''
		index = 0
		while(alive):
			if(state == 0):
				# Handshake message
				msg = mpc.msg_handshake(peer_parameters)
				sock.send(msg)

			if(state == 2):
				lock_rarest.acquire()
				# Increment the count of all available pieces
				p =1
				#'bitfield' is only ever sent as the first message. 
				#Its payload is a bitfield with each index that downloader has sent set to one and the rest set to zero. 
				#Downloaders which don't have anything yet may skip the 'bitfield' message. 
				#The first byte of the bitfield corresponds to indices 0 - 7 from high bit to low bit, respectively. 
				#The next one 8-15, etc. Spare bits at the end are set to zero
				for i in range(0,len(bitfield)):
					x = unpack("B",bitfield[i:i+1])[0]
					q = 1
					for j in range(0,8):
						if(x & 1<<j):
							piece_parameters[p*8-q]["count"] = piece_parameters[p*8-q]["count"] + 1
						q = q+1	
					p=p+1
				# Sort received peices for rarest first algorithm as per count parameter
				list_rarest = sorted(piece_parameters, key = lambda i: i['count'])
				lock_rarest.release()	
				# Build and send Interested message over Socket
				
				# INTERESTED 
				msg = mpc.msg_interested()
            		
				try:
					sock.send(msg)
				except Exception as e:
					pass

			# Peer is Unchoked
			
			if(state == 3):
				checkpt = True
				for i in range(0, len(list_rarest)):
					p = math.floor(list_rarest[i]['index']/8) + 1
					x = unpack("B",bitfield[p-1:p])[0]
					q = 1					
					for j in range(0,8):
						bit_index = p*8-q
						if(x & 1<<j):
							if(bit_index == list_rarest[i]['index']):
								if(bit_index == len(metadata['info']['pieces'])-1):
									piece_length = metadata['info']['length'] - (bit_index)*metadata["info"]['piece length']
								else:
									piece_length = metadata["info"]['piece length']
									
								if piece_parameters[bit_index]["done"] == False and (piece_parameters[bit_index]["downloading"] == False  or piece_parameters[bit_index]["downloading_peer"] == peer_id ):
									
									piece_parameters[bit_index]["downloading_peer"] = peer_id
									# Check for Remaining Piece Length
									incomplete = piece_length - piece_parameters[bit_index]["offset"]
									index, offset = bit_index,piece_parameters[bit_index]["offset"]
									# Apply max piece length

									if(incomplete > 2**14):
										piece_len = 2**14
									else:
										piece_len = incomplete
									lock_piece.acquire()			
									piece_parameters[bit_index]["downloading"] = True
									lock_piece.release()
									checkpt = False
									break		
						else:
							pass
						q = q+1	
					if(checkpt == False):
						break
				if(checkpt):
					alive = 0
					break
				
				# Send piece request				
        		# REQUEST 
				#'request' messages contain an index, begin, and length. 
				#The last two are byte offsets. Length is generally a power of two unless it gets truncated by the end of the file. 
				#All current implementations use 2^14 (16 kiB), and close connections which request an amount greater than that
				msg = mpc.msg_piece_req(index,offset,piece_len)		
				sock.send(msg)
			
			# Receiving of response from peers		
			time1 = time.time()
			response = sock.recv(2**20)
			time2 = time.time()
			if(torrent_parameters['maxm_speed_download'] != 0):
				time_real = time2-time1
				time_req = (len(response)/1000)/torrent_parameters['maxm_speed_download']
				if(time_req > time_real):
					time.sleep(time_req - time_real)
					time2 = time.time()	

			if(list_peers[peer_index]['speed_download'] == 0):
				list_peers[peer_index]['speed_download'] = ((len(response)/1000)/(time2 - time1))  
			else: 
				list_peers[peer_index]['speed_download'] = round((list_peers[peer_index]['speed_download'] + ((len(response)/1000)/(time2 - time1)))/2,3)
			
			if(len(response) == 0):
				raise Exception("Connection lost! No Response!")
				state = 0
				continue

			if(state == 0):
				if len(response) < 68:
					break
				else:
					handshake = unpack('!s19sii20s20s',response[:68])
					peer_id = handshake[5]
					# Change state to Handshake Done
					state = 1
					response = response[68:]	
			packet_len = len(response)

			while(packet_len > 0):			
				
				#all payload lengths are 4 bytes for all types
				
				length = mpc.calc_len(response)
				if(length == 0):
					break
				msg_type, response = mpc.find_msg_type(response)
				
				'''types = {
					    0: Choke, CHOKE = <length><message_id>
					    1: UnChoke, UnChoke = <length><message_id>
					    2: Interested, INTERESTED = <length><message_id>
					    3: NotInterested,
					    4: Have, HAVE = <length><message_id><piece_index>
					    5: BitField,  BITFIELD = <length><message id><bitfield>
					    6: Request, REQUEST = <length><message id><piece index><block offset><block length>
					    7: Piece, PIECE = <length><message id><piece index><block offset><block>
					}
						'''
						            		
    				# type 0 = choke / kill connection	
				if(msg_type == 0):
					alive = 0
					break
					
    				# type 5 = bitfield , - bitfield = bitfield representing downloaded pieces (bitfield_size bytes)
				if(msg_type == 5):
					if(len(response) >= length-1):
						bitfield = unpack(str(length-1)+'s',response[:length-1])[0]
						response = response[length:]
						# Change State to Got bitfield
						state = 2
						break
					else:	
						bitfield = unpack(str(len(response))+'s', response)[0]
					
					bit_incomplete = length-1 - len(response)
					response = response[len(response):]

					while(bit_incomplete > 0):
						time1 = time.time()
						bit_left = sock.recv(4096)
						time2 = time.time()
						if(torrent_parameters['maxm_speed_download'] != 0):
							time_real = time2-time1
							time_req = (len(bit_left)/1000)/torrent_parameters['maxm_speed_download']
							if(time_req > time_real):
								time.sleep(time_req - time_real)
								time2 = time.time()

						if(list_peers[peer_index]['speed_download'] == 0):
							list_peers[peer_index]['speed_download'] = ((len(bit_left)/1000)/(time2 - time1))  
						else: 
							list_peers[peer_index]['speed_download'] = round((list_peers[peer_index]['speed_download'] + ((len(bit_left) * 0.001)/(time2 - time1)))/2,3)
						
						if(len(bit_left) > bit_incomplete):
							bitfield = bitfield + unpack(str(bit_incomplete) + 's', bit_left[:bit_incomplete])[0]
							response = bit_left[bit_incomplete:]
							break
						else:
							bitfield = bitfield + unpack(str(len(bit_left))+'s', bit_left)[0]
							bit_incomplete = bit_incomplete - len(bit_left)	
						
					if(math.ceil(math.log(len(bitfield)*8,2)) == math.ceil(math.log(len(metadata['info']['pieces']),2))):
						state = 2		
						
				# type 1 = unchoke
				if(msg_type == 1):
					state = 3
				
				#type 4 = have piece, - piece_index = zero based index of the piece (4 bytes) 
				if(msg_type == 4):
					response = response[4:]

				#type 7 = piece block receive	
        			# 	- block = block as a bytestring or bytearray (block_len bytes)    			
				if(msg_type == 7):
					# - length = 9 + block length (4 bytes)
					left_piece_len = length -9
					# 	- piece index =  zero based piece index (4 bytes)
        			# 	- block offset = zero based of the requested block (4 bytes)
					index, offset = unpack('!II',response[:8])
					#print("receiving block ",index,"offset at",offset,"of length",length-9)
					response = response[8:]

					if(len(response) > left_piece_len):
						block = unpack(str(left_piece_len)+"s",response[:left_piece_len])[0]
						left_piece_len = left_piece_len - len(response)
						response = response[left_piece_len:]
						break
					else:
						block = unpack(str(len(response))+'s',response)[0]
						left_piece_len = left_piece_len - len(response)
						response = response[len(response):]	

					while(left_piece_len > 0):
						time1 = time.time()
						block_left = sock.recv(2**16)
						time2 = time.time()
						if(torrent_parameters['maxm_speed_download'] != 0):
							time_real = time2-time1
							time_req = (len(block_left)/1000)/torrent_parameters['maxm_speed_download']
							if(time_req > time_real):
								time.sleep(time_req - time_real)
								time2 = time.time()

						if(list_peers[peer_index]['speed_download'] == 0):
							list_peers[peer_index]['speed_download'] = ((len(block_left) * 0.001)/(time2 - time1))  
						else: 
							list_peers[peer_index]['speed_download'] = round((list_peers[peer_index]['speed_download'] + ((len(block_left) * 0.001)/(time2 - time1)))/2,3)

						if(len(block_left) >= left_piece_len):	
							block = block + unpack(str(left_piece_len)+'s',block_left[:left_piece_len])[0]
							left_piece_len = left_piece_len - len(block_left)
						else:
							block = block + unpack(str(len(block_left))+'s', block_left)[0]
							left_piece_len = left_piece_len - len(block_left)
					
					writing_piece_into_file(index,offset,block)
					piece_parameters[index]['offset'] = piece_parameters[index]['offset'] + len(block) 
					
					if(index == (len(metadata['info']['pieces'])-1)):
						if(piece_parameters[index]['offset'] == (metadata['info']['length'] - (index * metadata['info']['piece length']))):
							block_hash = hashlib.sha1(reading_piece_from_file(index)).hexdigest()
							if(block_hash == metadata['info']['pieces'][index]):
								piece_parameters[index]["done"] = True
								piece_parameters[index]["downloading"] = False
								torrent_parameters['pieces_downloaded'] += 1
								break
							else:
								piece_parameters[index]["offset"] = 0
								piece_parameters[index]["downloading"] = False
								break
					else:			
						if(piece_parameters[index]['offset'] == metadata['info']['piece length']):
							
							block_hash = hashlib.sha1(reading_piece_from_file(index)).hexdigest()
							if(block_hash == metadata['info']['pieces'][index]):
								piece_parameters[index]["done"] = True
								piece_parameters[index]["downloading"] = False	
								torrent_parameters['pieces_downloaded'] += 1
								break
							else:
								piece_parameters[index]["offset"] = 0
								piece_parameters[index]["downloading"] = False	
								break
				packet_len = len(response)
					
	except Exception as e:
		piece_parameters[index]["downloading"] = False		
				

#_____________________________PART 4 : Write/Read Pieces & Progress Report:_______________________________________________________
# Function to write a piece to file
def writing_piece_into_file(index,offset,block):
	file_download.seek((index * metadata['info']['piece length'])+offset,0)
	file_download.write(block)

# Function to read a piece from file
def reading_piece_from_file(index):
	file_download.seek((index * metadata['info']['piece length']),0)
	if(index == len(metadata['info']['pieces'])-1):
		piece = file_download.read(metadata['info']['length'] - (index * metadata['info']['piece length']))
	else:
		piece = file_download.read( metadata['info']['piece length'])
	return piece	

# Function to display download_percentage report
def progress_report():
	global torrent_parameters
	download_percentage = 0
	while(download_percentage != 100):
		download_percentage = round(torrent_parameters['pieces_downloaded']/len(metadata['info']['pieces'])*100,2)
		print("Downloaded", download_percentage,"%", end = "\r")
		time.sleep(0.2)
	print("Download Complete!")
	

#_____________________________PART 5 : Application:________________________________________________________________________________
while(torrent_parameters['pieces_downloaded'] != len(metadata['info']['pieces'])):
	print("Please Wait, Extracting Peer Information from Trackers!")
	get_peers_from_trackers(metadata,peer_parameters)						
	print("No of peers found : ",len(list_peers))
	peer_threads = []

	for peer in list_peers:
		peer['speed_download'] = 0
	# Handle simultaneous peer communication using Threads
	for peer in list_peers:
			peer_threads.append(Thread(target = peer_handler, args = (peer['ip'],peer['port'],peer_parameters, list_peers.index(peer),torrent_parameters)))
			
	print("Downloading Started!")
	# Print overall download_percentage
	Thread(target = progress_report).start()	
	
	# Start threads
	for thread in peer_threads:
		thread.start()

	# Join threads
	for thread in peer_threads:
		thread.join()



#display all the required things asked to collect
disp = display()

disp.disp_list_track(metadata)
disp.disp_list_peers(list_peers)
disp.disp_list_pieces(piece_parameters)
disp.disp_rarest(list_rarest)
disp.disp_top4(list_peers)		
