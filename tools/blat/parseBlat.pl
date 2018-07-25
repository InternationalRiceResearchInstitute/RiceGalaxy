#!/usr/bin/perl
use warnings;

die "Usage: <script> alnFile outfile pctID misMatch maxNumGap\n" if (!@ARGV);

my $pctID = $ARGV[2]; ##  fraction of match vs query length
my $mismatch = $ARGV[3]; ## # mismatches allowed
my $maxgap = $ARGV[4]; ## max num gaps allowed
my $psl = $ARGV[0]; ##  alignment file name
my $output = $ARGV[1]; ## filtered file output
my $awkstring1 = " '" . '($1>=' ;
my $awkstring2 = '*$11) ' ;
my $awkstring3 = ' $2<=' ;
my $awkstring4 = '$5<=';
my $string4 = "' ";

#my $command = "awk ". $awkstring1 . $pctID . $awkstring2 . "&&" .  $awkstring3 .  $mismatch . $string4 . $psl . " >>" . $output ; ## command to pass to system call
my $command = "awk ". $awkstring1 . $pctID . $awkstring2 . "&&" .  $awkstring3 .  $mismatch . " && " . $awkstring4 .  $maxgap . $string4 . $psl . " >>" . $output ; ## command to pass to system call


#print $command;
system("head -5 $psl > $output"); ## preserve header columns
system ($command); ## awk command




