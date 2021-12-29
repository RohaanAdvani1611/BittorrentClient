import sys
import requests
import hashlib
import bencodepy
import random
from struct import *


# The first character of the format string can be used to indicate the byte order, size and alignment of the packed data
'''
	<	little-endian
	>	big-endian
	!	network (= big-endian)

'''	

# Format Characters , format string used here starts with one of '<', '>', '!'	
'''
	Format  Python type          Standard size
	x       no value
	c       bytes of length      1
	b       integer              1
	B       integer 	         1
	h       integer              2
	H       integer              2
	i       integer              4
	I       integer              4
	l       integer              4
	L       integer              4
	q       integer              8
	Q       integer              8
	n       integer
	N       integer
	e       float                2
	f	float       	     4
	d	float		         8
	s	bytes
	p	bytes
	P	integer

'''		
		
	
class msg_udp_tr():
	# Connection Request and Response
		
		#connect = <connection_id><action><transaction_id>
		#    - connection_id = 64-bit integer
		#    - action = 32-bit integer
		#    - transaction_id = 32-bit integer
		#Total length = 64 + 32 + 32 = 128 bytes


	def msg_conn(self):
		self.protocol_id = 0x41727101980
		self.act  = 0  # Action for connection
		self.transaction_id = random.randrange(0, 2147483647)
		d = pack('!qii',self.protocol_id,
				   self.act,
				   self.transaction_id)
		return d

	# IPV4 Announce Request
		
		# connect = <connection_id><action><transaction_id>
		# 0	64-bit integer	connection_id
		# 8	32-bit integer	action	1
		# 12	32-bit integer	transaction_id
		# 16	20-byte string	info_hash
		# 36	20-byte string	peer_id
		# 56	64-bit integer	downloaded
		# 64	64-bit integer	left
		# 72	64-bit integer	uploaded
		# 80	32-bit integer	event
		# 84	32-bit integer	IP address	0
		# 88	32-bit integer	key
		# 92	32-bit integer	num_want	-1
		# 96	16-bit integer	port
		
		#     - connection_id = 64-bit integer
		#     - action = 32-bit integer
		#     - transaction_id = 32-bit integer
		    
		# Total length = 64 + 32 + 32 = 128 bytes
		
	def ipv4_annouce_req(self,peer_parameters,connection_id):
		self.action  = 1 # Action for Announce 
		self.event = 0
		self.ip_address = 0
		self.key = random.randrange(0, 2147483647)
		self.num_want = -1 
		d = pack('!qii20s20sqqqiiiih',connection_id,
						   self.action,
						   self.transaction_id,
						   peer_parameters['info_hash'],
						   peer_parameters['peer_id'].encode(),
						   peer_parameters['downloaded'],
						   peer_parameters['left'],
						   peer_parameters['uploaded'],
						   self.event,
						   self.ip_address,
						   self.key,
						   self.num_want,
						   peer_parameters['port'])
		return d
		
	# IPV4 Announce Response
	
		# connect = <connection_id><action><transaction_id>

		# 0	32-bit integer	action	1
		# 4	32-bit integer	transaction_id
		# 8	32-bit integer	interval
		# 12	32-bit integer	leechers
		# 16	32-bit integer	seeders
		# 20 + 6 * n	32-bit integer	IP address
		# 24 + 6 * n	16-bit integer	TCP port
		# 20 + 6 * N
		
	def ipv4_announce_res(self,data):
		action, transaction_id_tmp, inteval, leechers, seeders = unpack('!iiiii',data[:20])	
		n = int((len(data)-20) / 6)
		response = unpack("!"+n*'BBBBH',data[20:])
		return response
		
		
class msg_peer_comm():
	# Handshake = <pstrlen><pstr><reserved><info_hash><peer_id>
            		# 	- pstrlen = length of pstr (1 byte)
            		# 	- pstr = string identifier of the protocol: "BitTorrent protocol" (19 bytes)
            		# 	- reserved = 8 reserved bytes indicating extensions to the protocol (8 bytes)
            		# 	- info_hash = hash of the value of the 'info' key of the torrent file (20 bytes)
            		# 	- peer_id = unique identifier of the Peer (20 bytes)

        		# Total length = payload length = 49 + len(pstr) = 68 bytes (for BitTorrent v1)
    				
	def msg_handshake(self,peer_parameters):
		# pstrlen
		self.pslen = chr(19)
		message = pack('!c19sii20s20s',self.pslen.encode(),b'BitTorrent protocol',0,0,peer_parameters['info_hash'],peer_parameters['peer_id'].encode())
		return message
	
	
	# INTERESTED = <length><message_id>
            		# 		- payload length = 1 (4 bytes)
            		# 		- message id = 2 (1 byte)
            		
	def msg_interested(self):
		message = pack('!IB',1,2)
		return message
	

        # REQUEST = <length><message id><piece index><block offset><block length>
            		# 	- payload length = 13 (4 bytes)
            		#	- message id = 6 (1 byte)
            		# 	- piece index = zero based piece index (4 bytes)
            		#	- block offset = zero based of the requested block (4 bytes)
            		# 	- block length = length of the requested block (4 bytes)
            		
	def msg_piece_req(self,index,offset,piece_len):		
		message = pack('!IBIII',13,6,index,offset,piece_len)
		return message
		
		
	def calc_len(self,response):
		length = unpack("!I",response[:4])[0]
		return length
		
	def find_msg_type(self, response):
		type_m = unpack("!B",response[4:5])[0]
		response = response[5:]
		return type_m, response
		
	
		
		
		
		
