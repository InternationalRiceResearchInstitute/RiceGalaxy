<%
    import sys
    import os
    import re

    plugin_path=os.path.dirname(os.path.dirname(os.path.abspath(context['local'].filename)))
    if plugin_path not in sys.path:
	sys.path.append(plugin_path)
    print os.path.dirname(os.path.abspath(sys.argv[0]))
    root        = h.url_for( "/" )
    app_root    = root + "plugins/visualizations/sniplayvisu/static/"
%>


<!DOCTYPE HTML>
<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <title>SNiPlay : ${hda.name} visualization</title>

        ## install shared libraries
        ${h.js( 'libs/jquery/jquery',
                'libs/jquery/select2',
                'libs/bootstrap',
                'libs/underscore',
                'libs/backbone/backbone',
                'libs/require',
                'libs/d3')}

        ## shared css
        ${h.css( 'base' )}


        ## install default css
        ${h.stylesheet_link( app_root+"highslide.css" )}

	## highchart
	${h.javascript_link( app_root+"highcharts.js" )}
        ${h.javascript_link( app_root+"highcharts-more.js" )}
	${h.javascript_link( app_root+"data.js" )}
	${h.javascript_link( app_root+"exporting.js" )} 
	${h.javascript_link( app_root+"heatmap.js" )} 
	${h.javascript_link( app_root+"highcharts-3d.js" )}

	## Additional files for the Highslide popup effect
	${h.javascript_link( app_root+"highslide-full.min.js" )}
        ${h.javascript_link( app_root+"highslide.config.js" )}
	##${h.javascript_link( app_root+"highslide.config.js" )}

	## plugin pour Alexis
	## ${h.javascript_link( "http://sniplay.southgreen.fr/javascript/highslide.config.js" )}
	## ${h.stylesheet_link( "http://sniplay.southgreen.fr/styles/multiple_chr.css" )}	
    </head>

<%
    from create_conf_and_parse_xml import create_conf 
 
    directory=hda.file_name[:-4]+'_files/'
    tmp_file=''
    dataset_id= query['dataset_id'] 
    if not os.path.exists(directory):
    	os.makedirs(directory)


    input_params=hda.creating_job.raw_param_dict()
    
    def calcul_nb_chrom(file_name):
	nb_chr=int(os.popen('cut -f1 %s | uniq | wc -l'%file_name).read())-1
	per_chrom=''
        if nb_chr==1:
                per_chrom='off'
        elif nb_chr>1:
                per_chrom='on'
	return per_chrom

    def set_select_box(opt_list):
	OPTIONS='Display: <select name="display" id="display" onchange="reload();">\n'
	for v in opt_list:
		OPTIONS+='<option value="%s"'%v[0]
		if display_type==v[0] :
			OPTIONS+=' selected="selected"'
		OPTIONS+='>%s</option>\n'%v[1]

	OPTIONS+='</select>\n'
	return OPTIONS

    def check_datatype():
	if hda.datatype.__class__.__name__!="Text":
		return "Please convert your file in txt format, or ask your admin to install the latest wrapper version."
	else : 
		return ''

    BODY=''
    OPTIONS=''

    #### ****** Visualisation for MDS plot **********

    if hda.creating_job.tool_id in ['toolshed.g2.bx.psu.edu/repos/dereeper/sniplay/sniplay_mdsplot/1.1.1','toolshed.g2.bx.psu.edu/repos/dereeper/sniplay/sniplay_mdsplot/1.2.0'] :
    	if  hda.name.split(".")[-2]=='ibs_matrix' : ## MDS plot - file .ibs_matrix.txt
		BODY=check_datatype()
        	arguments={'select_title':'IBS matrix','per_chrom':'off', 'title': 'IBS matrix','subtitle': '', 'type':'heatmap', 'stacking':'off','yAxis':'Individuals','colors':"[0, '#FFFFFF'],[1, '#DF0101']",'file':hda.file_name}
    	elif  hda.name.split(".")[-2]=='mds_plot' : ## MDS plot - file .mds_plot.txt
		BODY=check_datatype()
		arguments={'select_title':'MDS plot (2D)','per_chrom':'off', 'title': 'MDS Plot (2D)','subtitle': '', 'type':'scatter', 'stacking':'off','yAxis':'PC1','xAxis':'PC2','point_size':5,'file':hda.file_name}
    	else :
	        BODY='Visualisation not available for this file. If you want to visualize your data, please choose .ibs_matrix.txt or .mds_plot.txt file.'



    #### ****** Visualisation for VCFtools SlidingWindows **********

    elif  hda.creating_job.tool_id in ['toolshed.g2.bx.psu.edu/repos/gandres/vcftools_filter_stats_diversity/sniplay_vcftoolsslidingwindow/1.0.0','localhost:9009/repos/gandres/vcftools_filter_stats_diversity5/sniplay_vcftoolsslidingwindow/1.1.0','toolshed.g2.bx.psu.edu/repos/gandres/vcftools_filter_stats_diversity/sniplay_vcftoolsslidingwindow/1.1.0','toolshed.g2.bx.psu.edu/repos/gandres/vcftools_filter_stats_diversity/sniplay_vcftoolsslidingwindow/1.2.0','toolshed.g2.bx.psu.edu/repos/gandres/vcftools_filter_stats_diversity/sniplay_vcftoolsslidingwindow/1.3.0','sniplay_vcftoolsslidingwindow'] :
        per_chrom=calcul_nb_chrom(hda.file_name)
        if per_chrom=='':
                BODY='Empty file ...'
	
	window=input_params['window'][1:-1]

    	if hda.name.split(".")[-1]=='pi':  ## VCFtools SlidingWindows - file .windowed.pi
		BODY=check_datatype()
		tmp_file=directory+'out.pi.tab'
		os.system('cut -f1,2,5 %s > %s'%(hda.file_name,tmp_file))
		arguments={'select_title':'Pi','per_chrom':per_chrom, 'title': 'Pi','subtitle': 'Sliding window : %s pb'%window, 'type':'area', 'stacking':'off','yAxis':'Pi','file':tmp_file}   
	elif hda.name.split(".")[-1]=='TsTv':  ## VCFtools SlidingWindows - file .TsTv
		BODY=check_datatype()
		tmp_file=directory+'out.TsTv.tab'
                os.system('cut -f1,2,4 %s > %s'%(hda.file_name,tmp_file))
                arguments={'select_title':'TsTv','per_chrom':per_chrom, 'title': 'TsTv','subtitle': 'Sliding window : %s pb'%window, 'type':'area', 'stacking':'off','yAxis':'TsTv','file':tmp_file}
	elif hda.name.split(".")[-1]=='snpden':  ## VCFtools SlidingWindows - file .snpden
		BODY=check_datatype()
		tmp_file=directory+'out.snpden.tab'
                os.system('cut -f1,2,4 %s > %s'%(hda.file_name,tmp_file))
                arguments={'select_title':'SNP density','per_chrom':per_chrom, 'title': 'SNP density','subtitle': 'Sliding window : %s pb'%window, 'type':'area', 'stacking':'off','yAxis':'SNPs','file':tmp_file}
	elif hda.name.split(".")[-1]=='D':  ## VCFtools SlidingWindows - file .Tajima.D
		BODY=check_datatype()
                tmp_file=directory+'out.TajD.tab'
                os.system('cut -f1,2,4 %s > %s'%(hda.file_name,tmp_file))
		os.system("sed -i 's/nan/0/g' %s"%tmp_file)
                arguments={'select_title':'Tajima','per_chrom':per_chrom, 'title': 'Tajima','subtitle': 'Sliding window : %s pb'%window, 'type':'area', 'stacking':'off','yAxis':'Tajima','file':tmp_file}
	#################### files with group option ##################################
	elif hda.name.split(".")[-2]=='fst' : ## VCFtools SlidingWindows - file .fst.txt
		BODY=check_datatype()
		arguments={'select_title':'FST','per_chrom':per_chrom, 'title': 'FST','subtitle': 'WEIGHTED_FST', 'type':'area', 'stacking':'off','yAxis':'FST','file':hda.file_name}
	elif hda.name.split(".")[-2]=='dtajima' : ## VCFtools SlidingWindows - file .combined.dtajima.txt
                BODY=check_datatype()
                if per_chrom=='on':
                        opt_list=[]
                        list_chr=os.popen('cut -f1 %s | sort -u '%hda.file_name).read().split('\n')

                        display_type=query['display']
                        if display_type=='None' :
                                display_type=list_chr[0] if list_chr[0]!="CHROM" else list_chr[1]
                        for chrom in list_chr :
                                if chrom not in ["Chromosome","CHROM",""]:
                                        opt_list.append((chrom,chrom))
                        OPTIONS=set_select_box(opt_list)
                        tmp_file=directory+'_%s'%display_type
                        os.system('head -n1 %s > %s'%(hda.file_name,tmp_file))
                        os.system("grep %s %s  >> %s"%(display_type,hda.file_name,tmp_file))
                        per_chrom='off'

                arguments={'select_title':'Tajima Combined','per_chrom':'off', 'title': 'Tajima Combined','subtitle': 'Sliding window : %s pb'%window, 'type':'line', 'stacking':'off','yAxis':'Tajima','file':tmp_file}
	elif hda.name.split(".")[-2]=='pi' : ## VCFtools SlidingWindows - file .combined.pi.txt
                BODY=check_datatype()
                if per_chrom=='on':
                        opt_list=[]
                        list_chr=os.popen('cut -f1 %s | sort -u '%hda.file_name).read().split('\n')

                        display_type=query['display']
                        if display_type=='None' :
                                display_type=list_chr[0] if list_chr[0]!="CHROM" else list_chr[1]
                        for chrom in list_chr :
                                if chrom not in ["Chromosome","CHROM",""]:
                                        opt_list.append((chrom,chrom))
                        OPTIONS=set_select_box(opt_list)
                        tmp_file=directory+'_%s'%display_type
                        os.system('head -n1 %s > %s'%(hda.file_name,tmp_file))
                        os.system("grep %s %s  >> %s"%(display_type,hda.file_name,tmp_file))
                        per_chrom='off'

                arguments={'select_title':'Pi Combined','per_chrom':'off', 'title': 'Pi Combined','subtitle': 'Sliding window : %s pb'%window, 'type':'line', 'stacking':'off','yAxis':'Pi','file':tmp_file}
	elif hda.name.split(".")[-2]=='genes' : ## VCFtools SlidingWindows - file .fst.bymarker.genes.txt
		BODY=check_datatype()
		opt_list=[]
		for chrom in os.popen('cut -f1 %s | sort -u'%hda.file_name).read().split('\n'):
			if chrom not in ["Chr","","Chromosome"]:	
				opt_list.append((chrom,chrom))

		display_type=query['display']
		if display_type=='None' :
			display_type=opt_list[0][0]

		tmp_file=directory+display_type
		print "**************************************************"
		print os.popen('wc -l %s'%hda.file_name).read()
		os.system("grep %s %s > %s"%(display_type,hda.file_name,tmp_file))
		arguments={'select_title':'FST by marker','per_chrom':'off', 'title': 'FST by marker','subtitle': '', 'type':'scatter', 'stacking':'off','yAxis':'FST','xAxis':'','point_size':5,'file':tmp_file}

                OPTIONS=set_select_box(opt_list)
		
 	else :
                BODY='Visualisation not available for this file. If you want to visualize your data, please choose .pi,.TsTV,.Tajima.D or .snpden file.'



    #### ****** Visualisation for VCFtools Stats **********

    elif hda.creating_job.tool_id in ['toolshed.g2.bx.psu.edu/repos/gandres/vcftools_filter_stats_diversity/sniplay_vcftoolsstats/1.0.0','toolshed.g2.bx.psu.edu/repos/gandres/vcftools_filter_stats_diversity/sniplay_vcftoolsstats/1.1.0'] :
    	if hda.name.split(".")[-2]=='TsTv': ## VCFtools Stats - file .TsTv.summary
		arguments={'select_title':'TsTv','per_chrom':'off', 'title': 'TsTv','subtitle': '', 'type':'pie', 'stacking':'off','file':hda.file_name,'categories':'Tv:AC,GT,CG,AT;Ts:AG,CT'}
    	elif  hda.name.split(".")[-1]=='annotation' : ## VCFtools Stats - file .annotation
		arguments={'select_title':'Genomic location','per_chrom':'off', 'title': 'Genomic location','subtitle': '', 'type':'pie', 'stacking':'off','file':hda.file_name,'categories':'Genic:Exon,Intron,UTR;Intergenic:Intergenic'}
		OPTIONS=set_select_box([("Genomiclocation","Genomic location"),("SNP_effect","SNP effect")])
	elif  hda.name.split(".")[-1]=='imiss':
		tmp_file=directory+'out.imiss'
		os.system('cut -f1,4 %s |sort -k2,2n > %s'%(hda.file_name,tmp_file))
		arguments={'select_title':'imiss','per_chrom':'off', 'title': 'imiss','subtitle': '', 'type':'column', 'stacking':'off','yAxis':'N_miss','xAxis':'individu','point_size':5,'file':tmp_file}
	elif  hda.name.split(".")[-1]=='het':
		tmp_file=directory+'out.het'
                os.system('cut -f1,3 %s |sort -k2,2n > %s'%(hda.file_name,tmp_file))
                arguments={'select_title':'het','per_chrom':'off', 'title': 'het','subtitle': '', 'type':'column', 'stacking':'off','yAxis':'% heterozygosity','xAxis':'individu','point_size':5,'file':tmp_file}
	else :
                BODY='Visualisation not available for this file. If you want to visualize your data, please choose .TsTv.summary or .annotation file.'



    #### ****** Visualisation for SNP density **********

    elif hda.creating_job.tool_id in ['toolshed.g2.bx.psu.edu/repos/dereeper/sniplay/sniplay_density/1.2.0','toolshed.g2.bx.psu.edu/repos/dereeper/sniplay/sniplay_density/1.3.0','toolshed.g2.bx.psu.edu/repos/dereeper/sniplay/sniplay_density/1.4.0','toolshed.g2.bx.psu.edu/repos/dereeper/sniplay/sniplay_density/2.0.0'] :
	per_chrom=calcul_nb_chrom(hda.file_name)
	if per_chrom=='':
		 BODY='Empty file ...'

    	if  hda.name.split(".")[-1]=='by_sample' : 
		BODY=check_datatype()
		file_to_visualize=hda.file_name
		if per_chrom=='on':
			opt_list=[]
			list_chr=os.popen('cut -f1 %s | uniq '%hda.file_name).read().split('\n')
			
			display_type=query['display']
	                if display_type=='None' :
				display_type=list_chr[0] if list_chr[0]!="Chromosome" else list_chr[1]
			for chrom in list_chr :
				if chrom not in ["Chromosome",""]:
					opt_list.append((chrom,chrom))
			OPTIONS=set_select_box(opt_list)
			tmp_file=directory+'_%s'%display_type
			step=input_params['step'][1:-1]
			os.system('head -n1 %s > %s'%(hda.file_name,tmp_file))
			#os.system("grep %s %s  | awk ' {print NR*%s,$2,$3,$4 }' | sed  's/ /\t/g' >> %s"%(display_type,hda.file_name,step,tmp_file))
                        os.system("grep %s %s  | awk ' { $1=NR*%s; print $0 }' | sed  's/ /\t/g' >> %s"%(display_type,hda.file_name,step,tmp_file))
			file_to_visualize=tmp_file
			per_chrom='off'
		
		arguments={'select_title':'SNPs density by sample','per_chrom':per_chrom, 'title': 'Density by sample','subtitle': '', 'type':'heatmap', 'stacking':'off','yAxis':'Samples','xAxis':'Position','colors':"[0, '#FFFFFF'],[1, '#DF0101']",'file':file_to_visualize}

    	elif hda.name.split(".")[-1]!='log' :
		BODY=check_datatype()
        	arguments={'select_title':'SNPs density','per_chrom':per_chrom, 'title': 'SNPs density','subtitle': '', 'type':'area', 'stacking':'off','yAxis':'SNPs','file':hda.file_name}
	else :
                BODY='Visualisation not available for this file. If you want to visualize your data, please choose .by_density or snp file.'



    #### ****** Visualisation for Tassel **********
    
    elif hda.creating_job.tool_id=='toolshed.g2.bx.psu.edu/repos/dereeper/tassel5/Tassel/5.0' :
	if  hda.name.split(" ")[-1]=='output' :
		chrom_list={'':0}
		trait_list=os.popen('cut -f1 %s | sort -u'%hda.file_name).read().split('\n')
		trait_list.remove('')
		trait_list.remove('Trait')
		tmp_file='suppression fichier trait actif'
		#for chrom in os.popen('cut -f3 %s | sort -u'%hda.file_name).read().split('\n'):
                #	if chrom not in ["Chr",""]:
                #        	chrom_list[chrom]=int(os.popen('grep %s %s | tail -n 1 | cut -f4'%(chrom,hda.file_name)).read())

		opt_list=[]
		print chrom_list
		for trait in trait_list: 
			opt_list.append((trait.replace(' ',''),trait))

		display_type=query['display']
		if display_type=='None' : 
			display_type=trait_list[0]
		
		tmpfile_name=directory+'tmp_file'
		formatedfile_name=directory+'%s.txt'%display_type
		os.system('grep %s %s | awk "{print \$3,\$2,\$4,-log(\$6)/log(10)}">%s'%(display_type,hda.file_name,tmpfile_name))

		for chrom in os.popen('cut -f3 %s | sort -u'%hda.file_name).read().split('\n'):
		        if chrom not in ["Chr",""]:
				chrom_list[chrom]=int(os.popen("awk '{ if($1==\"%s\") print $0}' %s| tail -n 1 | cut -d' ' -f3"%(chrom,tmpfile_name)).read())
		
		tmpfile=open(tmpfile_name,'r')
		formatedfile=open(formatedfile_name,'w')
		addon=0
		previous=''
		for line in tmpfile.xreadlines():
			tmp=line.split(' ')
			if previous != tmp[0]:
				addon+=chrom_list[previous]
				previous=tmp[0]
			tmp[2]=str(int(tmp[2])+addon)
			formatedfile.write('\t'.join(tmp))
		tmpfile.close()
		os.system('rm %s'%tmpfile_name)
		formatedfile.close()
		arguments={'select_title':'Tassel','per_chrom':'off', 'title': 'Tassel plot','subtitle': display_type, 'type':'scatter', 'stacking':'off','yAxis':'marker_p','xAxis':'','point_size':3,'file':formatedfile_name}
		
		OPTIONS=set_select_box(opt_list)
	elif  hda.name.split(" ")[-1]=='plot' : ## QQplot
		BODY=check_datatype()
		arguments={'select_title':'QQ plot','per_chrom':'off', 'title': 'QQ plot','subtitle': '', 'type':'scatter', 'stacking':'off','yAxis':'Observed (-log10 pval)','xAxis':'Expected (-log10 pval)','point_size':3,'file':hda.file_name}
	else : 
		BODY='Visualisation not available for this file. If you want to visualize your data, please choose Tassel output file.'

#    #### ****** Visualisation for Admixture **********
#
#	#### plus utile, comme admixture n est plus dans le workflow. Attention Bug visualisation, colonne trop grandes, disparition header pour all outputs pour K=3 par exemple. Voir CR20160411
#
#    elif hda.creating_job.tool_id=='toolshed.g2.bx.psu.edu/repos/dereeper/admixture/admixture/1.23' :
#	if  hda.name=='All Outputs':
#		check_datatype()
#                kmin=int(input_params['kmin'][1:-1])
#		kmax=int(input_params['kmax'][1:-1])
#		display_type=query['display']
#                if display_type=='None' :
#                        display_type=kmin
#		else : 
#			display_type=int(query['display'])
#		Kvalue=display_type
#		opt_list=[]
#		for k in range(kmin,kmax+1): 
#			opt_list.append((k,'K=%s'%k))
#			# parse file for create each k file
#		OPTIONS=set_select_box(opt_list)
#                tmp_file=directory+'K%s.txt'%Kvalue
#	
#		#### create tmp file for good K value
#		rang=Kvalue-kmin+1
#		liste_rang=['-2:']
#		liste_rang.extend(os.popen('grep -n == %s'%hda.file_name).read().split('\n'))
#		line_start=int(liste_rang[rang-1].split(':')[0])+3
#		line_stop=int(liste_rang[rang].split(':')[0])-3
#		donnees=os.popen("sed -n '%s,%sp' %s"%(line_start,line_stop,hda.file_name)).read().split('\n')
#		dataset_num=re.search('(^.*dataset_)(\d+)\.dat',hda.file_name)
#		file_traits=dataset_num.group(1)+str(int(dataset_num.group(2))-2)+'.dat'
#		traits=os.popen("cut -f1 %s"%file_traits).read().split('\n')
#		traits.pop(0)
#		file_tmp=open(tmp_file,'w')
#		header=traits.pop(0)
#		for i in range(0,len(donnees[0].split(' '))):
#			header+='\tQ%s'%(i+1)
#		header+='\n'
#		file_tmp.write(header)
#		for t,d in zip(traits,donnees) : 
#			file_tmp.write('%s\t%s\n'%(t,'\t'.join(d.split(' '))))
#		file_tmp.close()
#                arguments={'select_title':'Q estimates (K=%s)'%Kvalue,'per_chrom':'off', 'title': 'Q estimaties','subtitle': 'K=%s'%Kvalue, 'type':'column','group_padding':'0', 'stacking':'normal','yAxis':'Ancestry','xAxis':'Individuals','file':tmp_file}
#
#	elif hda.name=='Best K Output':
#		check_datatype()
#		tmp_file=directory+'tmp'
#		os.system("sed '1d' %s > %s"%(hda.file_name,tmp_file))
#		arguments={'select_title':'Best Q estimates','per_chrom':'off', 'title': 'Best Q estimaties','subtitle': '', 'type':'column','group_padding':'0', 'stacking':'normal','yAxis':'Ancestry','xAxis':'Individuals','file':tmp_file}
#        else :
#                BODY='Visualisation not available for this file. If you want to visualize your data, please choose "All Outputs" file or "Best K Output" file.'
#

   #### ****** Visualisation for sNMF **********
    elif hda.creating_job.tool_id=='toolshed.g2.bx.psu.edu/repos/dereeper/snmf/snmf/1.2' :
        if  hda.name=='Structure by sNMF':
                check_datatype()
                kmin=int(input_params['kmin'][1:-1])
                kmax=int(input_params['kmax'][1:-1])
                display_type=query['display']
                if display_type=='None' :
                        display_type=kmin
                else :
                        display_type=int(query['display'])
                Kvalue=display_type
                opt_list=[]
                for k in range(kmin,kmax+1):
                        opt_list.append((k,'K=%s'%k))
                        # parse file for create each k file
                OPTIONS=set_select_box(opt_list)
                tmp_file=directory+'K%s.txt'%Kvalue

                #### create tmp file for good K value
                rang=Kvalue-kmin+1
                liste_rang=['-2:']
                liste_rang.extend(os.popen('grep -n == %s'%hda.file_name).read().split('\n'))
                line_start=int(liste_rang[rang-1].split(':')[0])+3
                line_stop=int(liste_rang[rang].split(':')[0])-3
                donnees=os.system("sed -n '%s,%sp' %s > %s"%(line_start,line_stop,hda.file_name,tmp_file))
                arguments={'select_title':'Q estimates (K=%s)'%Kvalue,'per_chrom':'off', 'title': 'Q estimaties','subtitle': 'K=%s'%Kvalue, 'type':'column','group_padding':'0', 'stacking':'normal','yAxis':'Ancestry','xAxis':'Individuals','file':tmp_file}

        elif hda.name=='Best K Output':
                check_datatype()
                arguments={'select_title':'Best Q estimates','per_chrom':'off', 'title': 'Best Q estimaties','subtitle': '', 'type':'column','group_padding':'0', 'stacking':'normal','yAxis':'Ancestry','xAxis':'Individuals','file':hda.file_name}
        else :
                BODY='Visualisation not available for this file. If you want to visualize your data, please choose "Structure by sNMF" file or "Best K Output" file.'




    else :
	 
	BODY='Visualisation not available for this file. If you want to visualize your data, please try with an other file.'
	

    if not BODY : 
	#if isinstance(arguments,list):
	#	BODY=''
	#	count=0
	#	for arg in arguments :
	#		trait=arg['subtitle']
	#		print directory+'conf'
	#		create_conf(directory+trait+'-conf',arg)
	#		bodytmp=os.popen('{0}/chrom_viewer.pl {1}{2}-conf {1} |awk "/<body>/,/<\/body>/" | grep -v "\<body\>" | grep -v "\</body\> | "'.format(plugin_path,directory,trait)).read()
	#		os.system('mv {0}data.json {0}data-{1}.json'.format(directory,trait))
	#		BODY+=bodytmp.replace('id=\'plot\'','id=\'plot%s\''%count).replace('renderTo: \'plot\'','renderTo: \'plot%s\''%count).replace('data.json','data-%s.json'%trait)
	#		os.system("rm {0}{1}-conf".format(directory,trait))
	#		if tmp_file:
	#			os.system("rm %s%s.txt"%(directory,trait))
	#		count+=1
	#else : 
    	create_conf(directory+'conf',arguments)

    	BODY=os.popen('{0}/chrom_viewer.pl {1}conf {1} {2} {3}|awk "/<body>/,/<\/body>/" | grep -v "\<body\>" | grep -v "\</body\>"'.format(plugin_path,directory,root+'datasets/'+dataset_id+'/display','data.json')).read()
    	os.system("rm {0}conf".format(directory))
    	#if tmp_file:
	#	os.system("rm %s"%tmp_file)

    

%>

    <body>
${OPTIONS}
${BODY}
    </body>
</html>

