#!/usr/bin/env perl
use strict;
use warnings;
use Cwd qw(abs_path);
use File::Basename qw(dirname);
use File::Spec ();

require File::Spec->catfile(dirname(abs_path(__FILE__)), 'air_recording_supervisor.pl');

# Separate entry point preserves the existing session-only recording CLI.
my $code = eval {
    my $options = AirRecordingSupervisor::parse_cli_args(@ARGV);
    $options->{managed_start} = 1;
    AirRecordingSupervisor::run_supervisor($options);
};
if ($@) {
    # launchd output never includes arbitrary config/parser errors or secrets.
    print STDERR "Air login service failed; inspect private status and configuration.\n";
    exit 2;
}
exit(defined($code) ? $code : 0);
