#!/bin/bash

#PRESCRIPT_DEPS wget

mkdir vendor

DL https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css vendor/bootstrap.min.css
DL https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js vendor/bootstrap.bundle.min.js

exit 0
