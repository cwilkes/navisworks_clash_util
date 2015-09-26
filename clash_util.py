# imports modules
from xml.etree.ElementTree import parse
import xml.etree.ElementTree as ET
from ConfigParser import SafeConfigParser
import csv
import argparse
import sys


# pulls in data from .xml file
arg_parser = argparse.ArgumentParser(description="Group clashes in a Navisworks clash detective XML file.")
arg_parser.add_argument('CLASH_FILE', help="Clash XML file")
arg_parser.add_argument('--config_file', default="clash_util.ini", help="Name of the configuration file to use")
arg_parser.add_argument('--box_size', type=float, default="3.0", help="Size of the box in feet")
arg_parser.add_argument('--clash_output_filename', default="clash_group.csv", help="Name of output CSV")

args = arg_parser.parse_args()

# sets variables so that user can input parameters
config_file = args.config_file
box_size = args.box_size
clash_data_file = args.CLASH_FILE
clash_output_filename = args.clash_output_filename

doc = parse(clash_data_file)

config_parser = SafeConfigParser()
config_parser.read(config_file)

# creates header for csv file
CSV_HEADER = "CLASH_GROUP_NAME, ORIGIN_CLASH, CLASH_GROUP_COUNT, TOTAL_CLASHES, PATH_COMBO, PATH_BLAME, CLASH_DETAIL\n"

# create a list with path priority order
path_order = []
for path_order_num, path_file_name in config_parser.items("path"):
    path_order.append(path_file_name)

parsed_data = {}
clash_count = 0

# parse the XML data we care about
# first some summary information-including total number of clashes
for item in doc.iterfind('batchtest/clashtests/clashtest/summary'):
    clash_count = item.attrib['total']

# now some detail information about the clashes
# includes viewpoint, grid-location, and x,y,z location
for item in doc.iterfind('batchtest/clashtests/clashtest/clashresults/clashresult'):
    try:
        imagefile = item.attrib['href']
    except:
        imagefile = 'NA.jpg'
    name = item.attrib['name']
    file_keys = ""
    for plink in item.findall('clashobjects/clashobject/pathlink'):
        sys_elem =  plink[2].text.split('.')
        if len(file_keys) == 0:
            file_keys += sys_elem[0]
        else:
            file_keys += "-" + sys_elem[0]

    grid_location = ""
    for grid_line in item.findall('gridlocation'):
        if grid_line.text is not None:
            grid_location = grid_line.text.split(':')[0]

    for classp in item.findall('clashpoint/pos3f'):
        x = classp.attrib['x']
        y = classp.attrib['y']
        z = classp.attrib['z']
        coord = (x,y,z)
        parsed_data[coord] = (imagefile,name,file_keys, grid_location)

# now let's iterate and find the ones within a certain distance
results = {}
for x in parsed_data:
    group_size = 1
    group_file_key = ""

    clash1_image = parsed_data[x][0]
    clash1_name = parsed_data[x][1]
    clash1_file_key = parsed_data[x][2]
    clash1_grid_line = parsed_data[x][3]
    group_path_blame = ""
    # based on the precedence in the configuration file we need to attribute
    # this clash to one of the sub systems
    # first separate into two paths
    try:
        path1, path2 = clash1_file_key.split('-')
    except Exception as ex:
        #print >>sys.stderr, 'error with parsing clash1_file_key', ex
        path1, path2 = set(), set()
    # loop through path order.  We could use index, but we want to sub search
    # so doing this the hard way
    found = 0
    for p in path_order:
        # see if that path_order text is in either paths
        if p in path1:
            found = 1
            group_path_blame = path1
        elif p in path2:
            found = 1
            group_path_blame = path2

        if found:
            break

    # if we get here and haven't found anything our config is messed up, warn the user
    if not found:
        print "Could not find path order for %s.  Please check your config file." % clash1_file_key

    z1 = x[2]
    y1 = x[1]
    x1 = x[0]
    finds_key = [clash1_name]
    finds_source = clash1_name
    finds_data = [group_size, group_file_key, clash1_name, group_path_blame, (clash1_name, clash1_image, clash1_grid_line)]

    for y in parsed_data:
        clash2_image = parsed_data[y][0]
        clash2_name = parsed_data[y][1]
        clash2_file_key = parsed_data[y][2]
        clash2_grid_line = parsed_data[y][3]
        # skip if we are comparing a clash to itself
        if clash1_name == clash2_name:
            continue
        # skip if we are not comparing two clashes from the same sub system combination
        if clash1_file_key != clash2_file_key:
            continue

        # checks if a clash that is within the x,y bounds is also within the z bounds
        finds_data[1] = clash1_file_key
        z2 = y[2]
        y2 = y[1]
        x2 = y[0]
        zdelt = float(z1)-float(z2)
        if (zdelt >= -box_size) and (zdelt <=  box_size):
            ydelt = float(y1)-float(y2)
            if (ydelt >= -box_size) and (ydelt <= box_size):
                xdelt = float(x1)-float(x2)
                if (xdelt >= -box_size) and (xdelt <= box_size):
                    # found a clash  we care about
                    finds_key.append((clash2_name))
                    finds_data.append((clash2_name, clash2_image, clash2_grid_line))
                    finds_data[0] += 1

    # sort clash group name to remove duplicates using the built in Python sort
    s_finds_key = sorted(finds_key)
    s_finds_key_t = tuple(s_finds_key)
    if s_finds_key_t not in results.keys():
        results[s_finds_key_t] = finds_data

print "Found %s clash groups in %s total clashes" % (len(results), clash_count)

output_file = open(clash_output_filename, 'wb')
# writes data to .csv file
output_file.write(CSV_HEADER)
writer = csv.writer(output_file)
for clash_group, clash_data in results.items():
    print clash_group
    group_count = clash_data.pop(0)
    group_file_key = clash_data.pop(0)
    group_origin_clash = clash_data.pop(0)
    group_path_blame = clash_data.pop(0)
    writer.writerow([clash_group, group_origin_clash, group_count, clash_count, group_file_key, group_path_blame, clash_data])

output_file.close()

