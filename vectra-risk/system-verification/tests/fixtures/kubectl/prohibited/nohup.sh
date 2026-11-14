#!/bin/sh
nohup kubectl port-forward pod/x 80 &
