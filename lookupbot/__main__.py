#!/usr/bin/env python3
import logging
import yaml
import threading
import sys
import os
import getopt

from . import bot

def start_new_thread(func, join=False, args=(), kwargs=None):
	t = threading.Thread(target=func, args=args, kwargs=kwargs)
	if not join:
		t.daemon = True
	t.start()
	if join:
		t.join()

def usage():
	print("Usage: %s [-q] [-c file]" % sys.argv[0])
	print("Options:")
	print("  -h    Display this text")
	print("  -q    Quiet, set log level to WARNING")
	print("  -c    Location of config file (default: ./config.yaml)")

def main(configpath, loglevel=logging.INFO):
	with open(configpath, "r") as f:
		config = yaml.safe_load(f)

	logging.basicConfig(format="%(levelname)-7s [%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=loglevel)

	bot.init(config)

	try:
		start_new_thread(bot.run, join=True)
	except KeyboardInterrupt:
		logging.info("Interrupted, exiting")
		exit(1)

if __name__ == "__main__":
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hc:", ["help"])
	except getopt.GetoptError as e:
		print(str(e))
		exit(1)

	# Process command line args
	def readopt(name):
		for e in opts:
			if e[0] == name:
				return e[1]
	if readopt("-h") is not None or readopt("--help") is not None:
		usage()
		exit(0)
	configpath = "./config.yaml"
	if readopt("-c") is not None:
		configpath = readopt("-c")

	# Run the actual program
	main(configpath)
