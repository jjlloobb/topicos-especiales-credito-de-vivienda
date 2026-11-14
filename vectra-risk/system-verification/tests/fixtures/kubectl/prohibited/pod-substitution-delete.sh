#!/bin/sh
POD=$(kubectl get pods -o name)
POD2=$(kubectl delete pod x)
