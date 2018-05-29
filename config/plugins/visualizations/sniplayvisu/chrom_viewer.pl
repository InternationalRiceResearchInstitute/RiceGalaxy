#!/usr/bin/perl

use strict;
use warnings;
use Carp qw (cluck confess croak);

use File::Basename;
use Data::Dumper;

use CGI;


my $cgi = CGI->new();


my $chromosome = "All";
my $display = $cgi -> param('display');


my $config = $ARGV[0];

my $json_dir = $ARGV[1];
my $json_url = $ARGV[2];
my $datajson = $ARGV[3];
my $path;
my $suffix;


#( $json_url, $path, $suffix ) = fileparse( $json_dir, "\.[^.]*");
my $json_dir_name;
#($json_dir_name)=($json_url=~ m/(\d{3}\/\w+_files\/?)/);
#$json_url='http://galaxy4gwen.sb-roscoff.fr/galaxy/download/'.$json_dir_name.'/data.json';



my %CONFIG;
eval '%CONFIG = ( ' . `cat $config` . ')';
die "Error while loading configuration file: $@n" if $@;



sub log10 {
my $n = shift;
return log($n)/log(10);
}


my $chrom_to_display;
if ($chromosome)
{
	$chrom_to_display = $chromosome;
}

print $cgi->header();

print $cgi->start_html(
	-title  => "Chromosome viewer",
	-script => {
		'-language' => 'javascript', 
		'-src'		=> "http://coffee-genome.org/js/jquery-1.5.1.min.js"
    },

);

if (!$chrom_to_display){$chrom_to_display = "All";}


foreach my $key(sort keys(%CONFIG))
{
        if (!$display){$display=$key;}
}

my $split_per_chrom = $CONFIG{$display}{"per_chrom"};

my $ylabel = $CONFIG{$display}{"yAxis"};

my %xData;

my $file = $CONFIG{$display}{"file"};
my $type_display = $CONFIG{$display}{"type"};
my %chroms;
my %headers;
my %data;
my @inds;
my @xaxis;
my $max = 0;
open(my $F,$file) or die "Error while loading input file: $file";
my $numline = 0;
my $n = 0;
my $k_start = 2;
if ($type_display eq 'heatmap'){$k_start = 1;}
if ($type_display eq 'column'){$k_start = 1;}
if ($type_display eq 'scatter'){$k_start = 3;}

my $cat_pie;
my $data_pie = "";
my %chrom_numbers;
if ($type_display eq 'pie')
{	
	my @categories_pie;
	my $nsection = 0;
	my $categories_desc = $CONFIG{$display}{"categories"};
	if (!$chrom_to_display){
		while(<$F>)
		{
			my $line = $_;
			chomp($line);
			$line =~s/\n//g;
			$line =~s/\r//g;
			my @values = split(/\t/,$line);
			my $indice = $values[0];
			push(@categories_pie,$indice);
			my $val = $values[1];
			my @nbs;
			my @cat_interne;
			for (my $i = 2; $i <= $#values; $i++)
			{
				my ($type,$n) = split(":",$values[$i]);
				push(@nbs,$n);
				push(@cat_interne,$type);
			}
			my $cat_pie_interne = "'" . join("','",@cat_interne) . "'";
			my $nb_pie_interne = join(",",@nbs);
			$data_pie .= "{y: $val,color: colors[$nsection],drilldown: {name: '$indice',categories: [$cat_pie_interne],data: [$nb_pie_interne],color: colors[$nsection]}},";
			$nsection++;
		}
	}
	else {
		my %categories_description = ();
		my %categories_values = ();
		my @categories_string=split(/;/,$categories_desc);
		foreach my $cat (@categories_string)
		{
			my @tmp=split(/:/,$cat);
			my @tmp_subclasses=split(/,/,$tmp[1]);
			$categories_description{$tmp[0]}=\@tmp_subclasses;
			$categories_values{$tmp[0]}=0;
			foreach my $sublist (@tmp_subclasses)
			{
				$categories_values{$sublist}=0;
			}
		}
		while(<$F>)
		{
                        my $line = $_;
                        chomp($line);
                        $line =~s/\n//g;
                        $line =~s/\r//g;
			my @values = split(/\t/,$line);
			$categories_values{$values[0]}=$values[1];
		}
                #print Dumper(\%categories_values);
		my $nsection = 0;
		foreach my $cat_name (keys(%categories_description))
                {
			my $val=$categories_values{$cat_name};
			my $indice=$cat_name;
			my $cat_pie_interne="";
			my $nb_pie_interne="";
			#print "########## @{$categories_description{$cat_name}}\n";
			foreach my $subclass (@{$categories_description{$cat_name}})
			{

				$cat_pie_interne.="','".$subclass;
				$nb_pie_interne.=','.$categories_values{$subclass};
				#print "$categories_values{$subclass}  \n"
			}
			$cat_pie_interne = substr($cat_pie_interne, 2, length $cat_pie_interne)."'"; 
			$nb_pie_interne = substr($nb_pie_interne, 1, length $nb_pie_interne);
			$data_pie .= "{y: $val,color: colors[$nsection],drilldown: {name: '$indice',categories: [$cat_pie_interne],data: [$nb_pie_interne],color: colors[$nsection]}},";	
			$nsection++;
		}
		@categories_pie=keys(%categories_description)
	}
	$cat_pie = "'" . join("','",@categories_pie) . "'";
}
else
{
	my $max_val = 0;
	my $decalage = 0;
	my $track_num = 0;
	while(<$F>)
	{
		$numline++;
		my $line = $_;
		chomp($line);
		$line =~s/\n//g;
		$line =~s/\r//g;
		my @values = split(/\t/,$line);
		if ($numline == 1)
		{
			for (my $k = $k_start; $k <= $#values; $k++)
			{
				$headers{$k} = $values[$k];
				push(@inds,$headers{$k});
			}
		}
		else
		{
			my $chr = $values[0];
			if (!$chrom_numbers{$chr}){
				$chrom_numbers{$chr} = 1;
			}
			if (!$chrom_to_display or $CONFIG{$display}{"per_chrom"} eq "off")
			{
				$chrom_to_display=$chr;
				push(@xaxis,$chr);
			}
			my $x = $values[1];
			$chroms{$chr} = 1;
			if ($chr eq $chrom_to_display or $chrom_to_display eq 'All')
			{
				for (my $k = $k_start; $k <= $#values; $k++)
				{
					my $y = $values[$k];	
					if ($y > $max){$max = $y;}
					if ($type_display eq 'heatmap')
					{
						my $num = $k - 1;
						my $header = "";
						if ($headers{$k}){$header = $headers{$k};}
						$data{$header}.= "[$n,$num,$y],";
					}
					elsif ($type_display eq 'column')
					{
						$data{$headers{$k}}.= "$y,";
					}
					elsif ($type_display eq 'scatter')
					{
						#$data{$headers{$k}}.= "{name: '$chr',x: $x,y: $y},";
						my $name = $values[1];
						if ($values[4]){
							#$data{$values[0]}.= "{name: '$name',x: $values[2],y: $values[3],z: $values[4]},";
							$data{$values[0]}.= "{\"name\": \"$name\",\"x\": $values[2],\"y\": $values[3],\"z\": $values[4]},";
						}
						else{
							if ($ylabel eq "marker_p"){
								 if ($values[3] ne 'inf' && $values[3] > 0.5){
									#$data{$values[0]}.= "{name: '$name',x: $values[2],y: $values[3]},";
									$data{$values[0]} .= "{\"name\": \"$name\",\"x\":$values[2],\"y\":$values[3]},";
								}
							}
							else{
								$data{$values[0]} .= "{\"name\": \"$name\",\"x\":$values[2],\"y\":$values[3]},";
							}
						}
					}
					else
					{
						if ($chrom_to_display eq 'All'){
							my $ystart = $decalage;
                                        		$y = $ystart + $values[$k];
							if (!$decalage && $values[$k] > $max_val){$max_val=$values[$k];}
							#$data{$headers{$k}}{$chr}.= "[$x,$ystart,$y],";
							$data{$headers{$k}}{$chr}.= $values[$k].",";
							$xData{$x} = 1;
						}
						else{
							$data{$headers{$k}}.= "[$x,$y],";
						}
					}
				}
				$n++;
			}
		}
	}
}
close($F);


print "<br/><br/>";


my $colors = "[0, '#3060cf'],[0.5, '#fffbbc'],[0.9, '#c4463a'],[1, '#c4463a']";
if ($CONFIG{$display}{"colors"})
{
	$colors = $CONFIG{$display}{"colors"};
}

my $colorAxis = qq~
colorAxis: {
            stops: [
                $colors
            ],
            min: 0,
            max: $max,
            startOnTick: false,
            endOnTick: false,
            labels: {
                format: '{value}.'
            }
        },
~;
my $zoomType = "zoomType: 'xy',";
my $y_categories = "";
my $x_categories = "";
if ($type_display ne 'heatmap')
{
	$colorAxis = "";
	$zoomType = "zoomType: 'x',";
}

if ($type_display eq 'heatmap')
{
	$y_categories = "categories: ['" . join("','",@inds) . "'],";
	if (scalar @xaxis)
	{
		$x_categories = "categories: ['" . join("','",@xaxis) . "'],labels: {enabled:true, rotation: 90, align: 'left'},";
	}
}
if ($type_display eq 'column')
{
	if (scalar @xaxis)
	{
		$x_categories = "categories: ['" . join("','",@xaxis) . "'],labels: {enabled:true, rotation: 90, align: 'left'},";
	}
}


my $point_size = 3;
if ($CONFIG{$display}{"point_size"})
{
	$point_size = $CONFIG{$display}{"point_size"};
}


my $javascript = qq~
	
	<script type="text/javascript">
	
	function reload()
	{
		var display = document.getElementById('display').value;	
		var url = window.location.href; 
		var base_url = url.split('&');
		url = base_url[0];
		url += '&display='+display;
		window.location.href = url;
	}
	
	</script>
~;

print $javascript;

my $window_height = "800px";
if ($chrom_to_display eq 'All' && $type_display ne 'pie'){
	$window_height = (200 + (scalar keys %chrom_numbers) * 80) ."px";
	#$window_height = "900px";
}


my $html = qq~
	<div id='plot' style='min-width:120px;height:$window_height'></div>
	~;
print $html;

my $stacking = "";
if ($CONFIG{$display}{"stacking"} eq "normal")
{
	$stacking = "stacking: 'normal',";
}

my $tooltip = "";
my $plotline = "";
if ($type_display eq 'scatter')
{
	$tooltip = "tooltip: {headerFormat: '<b></b>',pointFormat: '<b>{point.name}'},";
	$plotline = "plotLines: [{value: 0,color: 'black',width: 2,}]";
}
my $options3D = "";
my $depth = "";
my $xAxis = "xAxis: {$x_categories title: {text: '$CONFIG{$display}{\"xAxis\"}'},$plotline},";
my $yAxis = "yAxis: {$y_categories title: {text: '$CONFIG{$display}{\"yAxis\"}'},$plotline},";

if ($chrom_to_display eq 'All'){
	$yAxis = "yAxis: {title:{text:'gfg',style:{'color':'white'}}, lineWidth: 0,minorGridLineWidth: 0,lineColor: 'transparent',labels: {enabled: false},minorTickLength: 0,tickLength: 0, gridLineColor:'white',},";
}

my $zAxis = "";
my $rotation_3d = "";
if ($CONFIG{$display}{"zAxis"})
{
	$options3D = "options3d: {enabled: true,alpha: 10,beta: 30,depth: 250,viewDistance: 5,}";
	$depth = "depth: 10,";
	$zoomType = "";
	$xAxis = "xAxis: {$x_categories title: {text: '$CONFIG{$display}{\"xAxis\"}'},},";
	$yAxis = "yAxis: {$y_categories title: {text: '$CONFIG{$display}{\"yAxis\"}'},},";
	$zAxis = "zAxis: {title: {text: '$CONFIG{$display}{\"zAxis\"}'},},";
	$rotation_3d = qq~
    \$(chart.container).bind('mousedown.hc touchstart.hc', function (e) {
        e = chart.pointer.normalize(e);

        var posX = e.pageX,
            posY = e.pageY,
            alpha = chart.options.chart.options3d.alpha,
            beta = chart.options.chart.options3d.beta,
            newAlpha,
            newBeta,
            sensitivity = 5; // lower is more sensitive

        \$(document).bind({
            'mousemove.hc touchdrag.hc': function (e) {
                // Run beta
                newBeta = beta + (posX - e.pageX) / sensitivity;
                chart.options.chart.options3d.beta = newBeta;

                // Run alpha
                newAlpha = alpha + (e.pageY - posY) / sensitivity;
                chart.options.chart.options3d.alpha = newAlpha;

                chart.redraw(false);
            },
            'mouseup touchend': function () {
                \$(document).unbind('.hc');
            }
        });
    });
	~;
}
my $pointer = "";
if ($CONFIG{$display}{"link"})
{
        my $jbrowse_link = $CONFIG{$display}{"link"};
        $pointer = qq~
	cursor:'pointer',
        point:
        {
                                                events: {
                                                        click: function (e) {
									pos = this.x;
                                                                        x = this.x - 20000;
                                                                        y = this.x + 20000;
								hs.graphicsDir = 'http://highslide.com/highslide/graphics/';
                                                                hs.outlineType = 'rounded-white';
                                                                hs.wrapperClassName = 'draggable-header';
                                                                hs.htmlExpand(null, {
                                                                        pageOrigin: {
                                                                                x: e.pageX,
                                                                                y: e.pageY
                                                                        },
                                                                        headingText: 'Links',
                                                                        maincontentText: '<a href=$jbrowse_link&loc=$chrom_to_display:'+x+'..'+y+'&highlight=$chrom_to_display:'+x+'..'+y+' target=_blank>View in JBrowse</a>',


                                    width: 200,
                                height:70
                                });
                            }
                        }
                    },
        ~;
	#$pointer = "";
}
my $title = $CONFIG{$display}{"title"};
my $subtitle = $CONFIG{$display}{"subtitle"};
if ($split_per_chrom eq "on")
{
	$title .= " ($chrom_to_display)";
}
	
#type: '$CONFIG{$display}{"type"}',

if ($type_display eq 'pie')
{
	my $javascript = qq~
	<script type='text/javascript'>
	\$(function () {

	
    var colors = Highcharts.getOptions().colors,
        categories = [$cat_pie],
        data = [$data_pie],
        browserData = [],
        versionsData = [],
        i,
        j,
        dataLen = data.length,
        drillDataLen,
        brightness;


    // Build the data arrays
    for (i = 0; i < dataLen; i += 1) {

        // add browser data
        browserData.push({
            name: categories[i],
            y: data[i].y,
            color: data[i].color
        });

        // add version data
        drillDataLen = data[i].drilldown.data.length;
        for (j = 0; j < drillDataLen; j += 1) {
            brightness = 0.2 - (j / drillDataLen) / 5;
            versionsData.push({
                name: data[i].drilldown.categories[j],
                y: data[i].drilldown.data[j],
                color: Highcharts.Color(data[i].color).brighten(brightness).get()
            });
        }
    }

	var chart;
		
							
	\$(document).ready(function() 
	{
		chart = new Highcharts.Chart({
				
			chart: {
					renderTo: 'plot',
					type: '$CONFIG{$display}{"type"}',
					$zoomType
				},
	
    
        title: 
		{
			text: '$title'
		},
		subtitle: 
		{
			text: '$subtitle'
		},
        
        plotOptions: {
            pie: {
                shadow: false,
                center: ['50%', '50%']
            }
        },
        series: [{
            name: 'TsTv',
            data: browserData,
            size: '60%',
            dataLabels: {
                formatter: function () {
                    return this.y > 5 ? this.point.name : null;
                },
                color: 'white',
                distance: -30
            }
        }, {
            name: 'TsTv',
            data: versionsData,
            size: '80%',
            innerSize: '60%',
            dataLabels: {
                formatter: function () {
                    // display only if larger than 1
                    return this.y > 1 ? '<b>' + this.point.name + ':</b> ' + this.y + ''  : null;
                }
            }
        }]
~;
	print $javascript;
}
else
{
	my $type_display = $CONFIG{$display}{"type"};
	#$yAxis = "";
	#$xAxis = "";
	my $javascript = qq~
<script type='text/javascript'>
		\$(function () {
		
		\$.getJSON('$json_url/$datajson', function (data) {

		var chart;
		
							
		\$(document).ready(function() {
			chart = new Highcharts.Chart({
				chart: {
					renderTo: 'plot',
					type: '$type_display',
					$zoomType
					$options3D
				},
				title: 
				{
					text: '$title'
				},
				subtitle: 
				{
					text: '$subtitle'
				},
				$yAxis
				$xAxis
				$zAxis
				$colorAxis
				plotOptions: {
 					$CONFIG{$display}{"type"}: {
 						$stacking
						$tooltip
						marker: {
							radius:$point_size,
						},
						turboThreshold:300000
					}
 				},
				series: ~;
	
	
if ($chrom_to_display eq "All"){

	##################################################################################
	# create json formatted file
	##################################################################################
	open(my $JSON,">$json_dir/$datajson");
	my $xData_string = join(",",sort {$a<=>$b} keys(%xData));
	my $nb_x = scalar keys(%xData);
	my $json_string = qq ~
{
    "xData": [$xData_string],
    "datasets": [
~;
	foreach my $header(keys(%data)){
		my $ref_hash = $data{$header};
		my %hash2 = %$ref_hash;
		foreach my $key(sort keys(%hash2)){
			my $chr_data = $data{$header}{$key};
			my $nb_data = scalar split(",",$chr_data);
			if ($nb_data < $nb_x){
				my $diff = $nb_x - $nb_data;
				$chr_data .= "0," x $diff;
			}			
			chop($chr_data);
			$json_string.= qq~
{
        "name": "$key",
        "data": [$chr_data],
        "unit": "Mb",
        "type": "area",
        "valueDecimals": 1
},~;
		}
	}
	chop($json_string);
	$json_string .= "]\n}";
	print $JSON $json_string;
	close($JSON);


	foreach my $header(keys(%data)){
	last;
		my $ref_hash = $data{$header};
		my %hash2 = %$ref_hash;
		foreach my $key(sort {$a<=>$b} keys(%hash2)){
			print "{\n";
			print "name: '$key',\n";
			print "color: '#1C485E',\n";
			print "type: 'arearange',\n";
			print "data: [" . $data{$header}{$key} . "],\n";
			print "marker: {radius:$point_size},\n";
			print "},\n";
			#print "{\n";
			#print "type: 'scatter',\n";
			#print "name: 'Events',color: '#333333',fillColor: 'rgba(255,255,255,0.8)',\n";
			#print "data: [[0,0]],\n";
			#print "\n";
			#print "},\n";
		}
	}
	$javascript = qq~
<script type='text/javascript'>
\$(function () {
    \$.getJSON('$json_url/$datajson', function (activity) {
        \$.each(activity.datasets, function (i, dataset) {

            // Add X values
            dataset.data = Highcharts.map(dataset.data, function (val, i) {
                return [activity.xData[i], val];
            });

            \$('<div class="chart_multi_chr">')
                .appendTo('#plot')
                .highcharts({
                    chart: {
                        marginLeft: 100, // Keep all charts left aligned
                        spacingTop: 0,
                        spacingBottom: 0,
                        //zoomType: 'x',
                        // pinchType: null // Disable zoom on touch devices
                    },
                    title: {
                        text: dataset.name,
                        align: 'left',
                        margin: 0,
                        ymargin: 10,
                        y: 80,
			x: 5
                    },	
                    credits: {
                        enabled: false
                    },
                    legend: {
                        enabled: false
                    },
                    xAxis: {
                        crosshair: true,
                      
                        labels: {
                            format: '{value}'
                        }
                    },
                    yAxis: {
                        title: {
                            text: null
                        }
                    },
                    series: [{
                        data: dataset.data,
                        name: dataset.name,
                        type: dataset.type,
                        color: Highcharts.getOptions().colors[3],
                        fillOpacity: 0.3,
                    }]

	});
~;
	print "<h1>$title</h1>";
	print "<h3>$subtitle</h3>";
	print $javascript;
}
else{
	

	print $javascript;
	print "data\n });\n";
	open(my $JSON,">$json_dir/$datajson");
        print $JSON "[\n";
        my $n = 0;
	foreach my $header(keys(%data)){
		#print "{\n";
		#print "name: '$header',\n";
		#print "data: [" . $data{$header} . "],\n";
		#if ($CONFIG{$display}{"group_padding"} eq "0")
		#{
		#	print "pointPadding: 0,\n";
		#	print "groupPadding: 0,\n";
		#}
		#print "marker: {radius:$point_size},\n";
		#print "$pointer\n";
		#print "},\n";


		my $data_value = $data{$header};
                chop($data_value);
                if ($n>0){print $JSON ",";}
                print $JSON "{\n";
                print $JSON "\"name\": \"$header\",\n";
                print $JSON "\"data\": [$data_value]\n";
                if ($CONFIG{$display}{"group_padding"} eq "0"){
                        print $JSON ",\"pointPadding\": 0,\n";
                        print $JSON "\"groupPadding\": 0\n";
                }
                print $JSON "}\n";
                $n++;
	}
	print $JSON "]\n";
        close($JSON);
}
}
my $javascript_end = qq~			
			});

		$rotation_3d
		});
	});

		
		</script>
    </body>
</html>
~;
print $javascript_end;
exit;
			






