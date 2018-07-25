#!/usr/bin/python

import multiprocessing as mp
import pandas as cute
import string
import random
import sys
import os

def sniff(inFile):
	# open file
	fh = open(inFile,'r')
	
	# see if there aee comments
	if()
	print(fileExt)
		

def testfxn(length,output):
	""" Generates a random string of numbers, lower- and uppercase chars. """
	rand_str = ''.join(random.choice(
                        string.ascii_lowercase
                        + string.ascii_uppercase
                        + string.digits)
        	    for i in range(length))
	output.put(rand_str)

if __name__ == "__main__":
	line = mp.Queue()
	cpuCount = mp.cpu_count()

	random.seed(123)
	#print(cpuCount) ## num of CPUs in this server = 2

	inputFile = sys.argv[1] # expect GOBII hapmap file
	coding = sys.argv[2] # expected coding: homoA, het, homoB, missing (separated by comma)
	outputFile = sys.argv[3]

	# Algorithm:
	# open the file
	# read file
	# get the allele matrix
	# chunck the allele matrix
	# do encoding
	
	#fileFormat = 
	sniff(inputFile)
	#print(fileFormat)
	#cute = read.table(inputFile)

	#processes = [mp.Process(target=testfxn,args=(20679,line)) for x in range(cpuCount)]

	#for p in processes:
	#	p.start()

	#for p in processes:
	#	p.join

	#results = [line.get() for p in processes]
	#print(results)
