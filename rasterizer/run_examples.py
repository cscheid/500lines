#!/usr/bin/env python

import rasterizer.examples as examples
from rasterizer import *
import subprocess

def run_example(example, filename):
    image = PPMImage(512, Color(1, 1, 1, 1))
    example.run(image)
    f = open(filename + '.ppm', 'w')
    image.write_ppm(f)
    f.close()
    subprocess.call(["convert", filename + '.ppm', filename + '.png'])

run_example(examples.e1, 'e1')
run_example(examples.destijl, 'destijl')
run_example(examples.e2, 'e2')
run_example(examples.e3, 'e3')

