# coding: utf-8


import argparse

def create_conf(path,args):
	f=open(path,'w')
	f.write("'%s'=>\n"%args['title'])
	f.write('{\n')
	for cle in args.keys():
		f.write('"%s" => "%s",\n'%(cle,args[cle]))
	f.write('},\n')
