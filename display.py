class display():
	def disp_help(self):
		print("BITTORRENT CLIENT:\n\n")
		print("Requirements:\n")
		print("pip3 install requests")
		print("pip3 install bencode.py\n\n")
		print("User can use following flags to configure settings\n")
		print("1) -d download speed")
		print("2) -u upload speed")
		print("3) -l download location")
		print("4) -p max number of peers\n\n")
		print("Here's how one can run the code:\n")
		print("python3 BittorrentClient.py torrent_file_name.torrent -d download_speed -u upload_speed -l download_location -p max_no_of_peers ")
		print("\n\nDevelopers-  Rohaan Advani & Varun Taneja")
		
	def disp_list_track(self, metadata):
		print("\n")
		print("--------------------------------------------LIST OF TRACKERS------------------------------------------------")
		print(metadata['announce'])
		for x in metadata['announce-list']:
			print(x)
			
	def disp_list_peers(self, list_peers):	
		print("\n")
		print("--------------------------------------------LIST OF PEERS---------------------------------------------------")
		for x in list_peers:
			print(x)
	
	def disp_list_pieces(self, rcv_pieces):
		print("\n")
		print("--------------------------------------------LIST OF PIECES---------------------------------------------------")
		for x in rcv_pieces:
			print(x)
	
	def disp_rarest(self, rarest):
		print("\n")	
		print("-------------------------------------RAREST PIECES IN ORDER---------------------------------------------")
		# Rarest piece order displayed
		for x in rarest:
			print(x['index'],end = " ")
		print("  ")
	
	def disp_top4(self, list_peers):
		print("\n")
		print("---------------------------------------------TOP 4 PEERS------------------------------------------------------")
		# Last 4 peers in sorted list is download speed
		for x in sorted(list_peers, key = lambda i: i['speed_download'], reverse = True)[:4]:
			print(x['ip'],"Download speed is",x['speed_download'],"Kbps")

