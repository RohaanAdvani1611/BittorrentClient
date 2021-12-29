import bencodepy
import sys
from struct import *

# Function opens file and gives control to dict_decoding
def torrent_file_decode(filename):
	torrent_file = open(filename , "rb")	
	decd_data = bencodepy.decode(torrent_file.read())
	torrent_file.close()
	return dict_decoding(decd_data) 

# Function to decode dictionaries, nested lists/dictionaries in metadata
def dict_decoding(dict_var):
	temp = {}
	for key,val in dict_var.items():		
		key = key.decode()		
		t = type(val)		
		if(key == 'pieces'):
			pieces = []
			# pieces maps to a string whose length is a multiple of 20. It is to be subdivided into strings of length 20, each of which is the SHA1 hash of the piece at the corresponding index
			for i in range(0,int(len(val)/20)):
				p = unpack("20s",val[:20])[0]
				pieces.append(p.hex())
				val = val[20:]
			val = pieces	
		elif(t is list):
			val = list_decoding(val)
		elif(t is dict):
			val = dict_decoding(val)
		elif(t is bytes):
			val = val.decode()
		temp[key] = val
	dict_var = temp		
	return dict_var				

# Helper Function
def list_decoding(list_var):
	temp = []
	for x in list_var:
		type_var = type(x)
		if(type_var is list):
			temp.append(list_decoding(x))
		elif(type_var is dict):
			temp.append(dict_decoding(x))
		elif(type_var is bytes):
			temp.append(x.decode())
	list_var = temp							
	return list_var		
