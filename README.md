# camerasync
Import and auto-process images from digital cameras

## Why?
I love to take pictures, but I hate to spend more time than necessary to manage them. I also dislike the editing process to make the pictures look better.

This tool helps me so that I can just mount the camera storage anywhere and then it will sync all new images to an archive, convert them to more portable formats, create HDR images of exposure bracketing sequences and save the output to one "to-check"-directory where I can go through the images with a simple image viewing program (such as geeqie) and move all images I like to album folders.

## What it does
1. Sync images from a camera mountpoint to a local archive (one way sync, adding new images to the archive)
1. Process the newly archived images and output files in the desired format to a "to-check"-directory
1. Detect bracketing sequences and attempt to create HDR images using configured tonemappings
1. If the process is aborted it will resume roughly where it stopped the next time the script is run.

## Requirements
* Python3
* pfstools
* imagemagick
* hugin (or at least the align_image_stack tool from hugin)
* ufraw
* exiftool

## Configuration
See the config.ini-sample file. Rename it to config.ini and place in the working directory or in ~/.config/camerasync/

## Usage
Create the configuration file and then run:

    python3 camera.py
    
You can also manually handle files by providing them as arguments. This is useful to reprocess some files or to test new settings.

    python3 camera.py <path to file1> ... <path to fileN>

## Questions?
This is a tool I created to solve a specific problem for me. If you have any questions about it, or would find it useful if it just had this one small feature, please let me know :)
