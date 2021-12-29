import sys 
import os
from display import display
import logging

class run():
	def start(self,torrent_parameters):
		if(sys.argv[2] == '-help'):
			disp = display()
			disp.disp_help()
			sys.exit(1)
						
		# System Arguments: -d(download speed), -u(upload speed), -l(download location), -p(max peers)
		if(len(sys.argv)<2):
			print("Invalid arguments")
			sys.exit(1)
		else:
			if(not os.path.isfile(sys.argv[1])):
				raise Exception()
			try:
				n = len(sys.argv)
				for i in range(2,n,2):
					if(sys.argv[i] == '-d'):
						torrent_parameters['maxm_speed_download'] = int(sys.argv[i+1])
					if(sys.argv[i] == '-u'):
						torrent_parameters['maxm_speed_upload'] = int(sys.argv[i+1])
					if(sys.argv[i] == '-l'):
						if(os.path.isdir(sys.argv[i+1])):
							torrent_parameters["download_location"] = sys.argv[i+1] + "/"
						else:
							raise Exception() 
					if(sys.argv[i] == '-p'):
						torrent_parameters['maxm_peers'] = int(sys.argv[i+1])					
			except Exception as e:
				#logging.exception(e)
				print("Invalid arguments")
				sys.exit(1)	
				
		return torrent_parameters
