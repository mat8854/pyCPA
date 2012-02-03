"""
| Copyright (C) 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

SMFF Loader/Annotation example
"""


import os
import string

from pycpa import analysis
from pycpa import smff_loader
from pycpa import graph
from pycpa import options

def smff_test(file):

    print "loading", file
    loader = smff_loader.SMFFLoader()
    s = loader.parse(file)

    # graph the smff system
    graph_file = string.replace(os.path.basename(file), ".xml", "") + ".pdf"
    print "generating system graph to", graph_file
    graph.graph_system(s, filename = graph_file)

    # analyze the system
    analysis.analyze_system(s)

    # print some analysis results
    print("Result:")
    print(s)
    for r in sorted(s.resources, key = str):
        print "results for resource %s" % r.name
        for t in sorted(r.tasks, key = str):
            print("%s - %d " % (str(t.name) , t.wcrt))

    # backannotate the xml
    loader.annotate_results()

    # write it
    loader.write(filename = "smff_annotated.xml")

if __name__ == "__main__":
    # this is necessary because the file is also called from the regression test suite
    default_file = os.path.dirname(os.path.realpath(__file__)) + "/smff_system.xml"

    options.parser.add_argument('--file', '-f', type = str, default = default_file,
                    help = 'File to load. Plot will be saved to FILE.pdf in current directory')


    options.init_pycpa()

    smff_test(options.opts.file)
