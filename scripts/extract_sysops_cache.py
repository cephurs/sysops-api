#!/usr/bin/python2.6
# filesource    \$HeadURL: svn+ssh://csvn@esv4-sysops-svn.corp.linkedin.com/export/content/sysops-svn/cfengine/branches/esv4-cfe-test.corp/generic_cf-agent_policies/config-general/manage_usr_local_utilities/extract_sysops_cache.py $
# version       \$Revision: 66239 $
# modifiedby    \$LastChangedBy: msvoboda $
# lastmodified  \$Date: 2013-10-14 18:11:59 +0000 (Mon, 14 Oct 2013) $

# (c) [2013] LinkedIn Corp. All rights reserved.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at  http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

from optparse import OptionParser
import sys
sys.path.append("/usr/local/admin")
import CacheExtractor
import difflib
import re
import hashlib
import seco.range

###############################################################################################
def build_valid_sites():
  range_query = "%cf3.promises.all-mps-cores"
  range_servers = []
  try:
    cm_conf = open("/etc/cm.conf", 'r')
    for line in cm_conf.readlines():
      if "MPS" in line:
        range_servers.append(line.split(':')[1].rstrip())
  except Exception, e:
    print e
    sys.exit(1)

  while range_servers:
    try:
      range_server = range_servers.pop()
      range_connection = seco.range.Range(range_server)
      total_redis_corelist = range_connection.expand(range_query)
      if total_redis_corelist:
        break
    except:
      pass

  """
  cf3.promises.eat1-22164-mps
  cf3.promises.ech3-32570-mps
  cf3.promises.ela4-41005-mps
  """
  sites = {}
  for core in total_redis_corelist:
    sites[core.split("-")[0].split(".")[2]] = 1

  uniq_sites = []
  for key in sites.iterkeys():
    uniq_sites.append(key)

  return(uniq_sites)
###############################################################################################
def validate_cli_args():
  if options.compare and options.search is None:
    print "To use the --compare function, we must find exactly one object with --search to compare against."
    sys.exit(1) 

  if options.compare_all and options.search is None:
    print "To use the --compare function, we must find exactly one object with --search to compare against."
    sys.exit(1) 

  if options.compare_all and options.compare:
    print "--compare-all must be used with --search.  It cant not be used with --compare.  --compare is a one to many comparsion.  --compare-all is a many to many."
    sys.exit(1)

  if options.hostlist and not options.compare_all:
    print "--hostlist is only used when executing --compare-all to display the matchines that matched a given md5sum in the cache"
    sys.exit(1)

  if options.list_files is None and options.info is None and options.search is None and options.compare_all is None:
    print "No valid option passed.  Exiting"
    sys.exit(1)

  if (options.contents	and (options.md5sum	or options.stat		or options.wordcount) or
     options.md5sum	and (options.contents	or options.stat		or options.wordcount) or
     options.stat	and (options.contents	or options.md5sum	or options.wordcount) or
     options.wordcount	and (options.contents	or options.md5sum	or options.stat)):
    print "You can only use --contents, --md5sum, --stat, or --wordcount.  Pick one."
    sys.exit(1)
 
  if options.range_query and options.site is None and options.scope != "global":
    print "You have specified to perform a search against range query " + options.range_query + " but did not specifiy a specific site / datacenter to search."
    print "Specifying a datacenter greatly reduces execution time as this utility performs site specific queries instead of global queries."  
    print "The available datacenters are "
    for site in sites:
      print site
    print "If you would like to search against a specific site, enter it below.  Otherwise, just hit enter. This argument can be passed on the CLI with --site."
    while True:
      second_chance = raw_input()
      if second_chance in sites:
        options.site = second_chance
        return
      elif second_chance == "":
        print "Executing a global query now.  Please wait..."
        return
      elif second_chance not in sites:
        print "Your entry  chance was " + second_chance + " which is not a valid site."
        print "Please enter a valid site, or just press enter to perform a global query."

###############################################################################################
def sanatize_compare_inputs(options,redisResults,compareResults):
  redisResultsLength = len(redisResults._gold.keys())
  if redisResultsLength != 1:
    print "Only one item can be used with --search when using --compare.  We found " + str(redisResultsLength) + " items from the search string:"
    print options.search
    print "You should narrow your search down so only a single item is returned.  Press any key to see the results that were returned."
    garbage = raw_input()
    for key in sorted(redisResults._gold.iterkeys()):
      print key
    sys.exit(1)
###############################################################################################
def compare_two_extracted_objects(key1, data1, key2, data2):
  differ = difflib.Differ()
  search_result = re.compile("^[-]")
  compare_result = re.compile("^[+]")
  matched_result = re.compile("^[ ]")
  search_string = key1.ljust(50)
  compare_string = key2.ljust(50)
  matched_string = "matching line".ljust(50)
  search_md5sum = hashlib.md5()
  compare_md5sum = hashlib.md5()
  search_md5sum.update(data1)
  compare_md5sum.update(data2)

  if search_md5sum.hexdigest() == compare_md5sum.hexdigest():
    if options.contents:
      print "contents of " + key1 + " and contents of " + key2 + " are identical"
    if options.md5sum:
      print "md5sum of " + key1 + " and md5sum of " + key2 + " are identical"
    if options.stat:
      print "os.stat() of " + key1 + " and os.stat() of " + key2 + " are identical"
    if options.wordcount:
      print "wordcount of " + key1 + " and wordcount of " + key2 + " are identical"
  else:
    results = []
    compare_array = list(differ.compare(data1.splitlines(), data2.splitlines()))
    for line in compare_array:
      if search_result.match(line):
        print search_result.sub(search_string + "\t", line)
      elif compare_result.match(line):
        print compare_result.sub(compare_string + "\t", line)
      elif matched_result.match(line):
        print matched_result.sub(matched_string + "\t", line)
  print
###############################################################################################
if __name__ == '__main__':

  # Before we attempt to accept CLI options, we need to know what the valid datacenters / sites are for the --site argument.  Query range.
  sites = build_valid_sites()

  parser = OptionParser(usage ="usage: %prog [options]",
    version ="%prog 1.0") 
  parser.add_option("--verbose",
    action = "store_true",
    dest = "verbose",
    default = False,
    help = "Enable verbose execution")
  parser.add_option("--list-files",
    action = "store_true",
    dest = "list_files",
    help = "List the available files which are stored within the cache")
  parser.add_option("--prefix-hostnames",
    action = "store_true",
    dest = "prefix_hostnames",
    help = "Prefix the hostname on every line of the contents of the extracted named object so to work with shell utilities")
  parser.add_option("--contents",
    action = "store_true",
    dest = "contents",
    help = "Print the contents of the file at the given name")
  parser.add_option("--md5sum",
    action = "store_true",
    dest = "md5sum",
    help = "Print the md5sum of the file at the given name")
  parser.add_option("--stat",
    action = "store_true",
    dest = "stat",
    help = "Print the stat of the file at the given name")
  parser.add_option("--wordcount",
    action = "store_true",
    dest = "wordcount",
    help = "Print the wordcount of the file at the given name")
  parser.add_option("--range-servers",
    action = "store",
    dest = "range_servers",
    help = "Specify which range servers you wish to query. This is optional.  If not provided, we will use the MPS in /etc/cm.conf")
  parser.add_option("--range-query",
    action = "store",
    dest = "range_query",
    help = "Specify a range cluster of hosts you which to use to use to make queries against.")
  parser.add_option("--scope",
    action = "store",
    dest = "scope",
    choices = ["global", "site", "local"],
    default = "local",
    help = "What scope do you want to query? local = query only my core. site = query entire datacenter. global = query all cores from all datacenter")
  parser.add_option("--site",
    action = "store",
    dest = "site",
    choices = sites,
    help = "If querying a specific site using --scope site, then specify which site/datacenter you which to query. Choices are " + str(sites))
  parser.add_option("--search",
    action = "store",
    dest = "search",
    help = "Provide a string that can be searched against via wildcards which will return available objects.  For example, providing 'mike' would perform a key search against '*mike*'")
  parser.add_option("--info",
    action = "store_true",
    dest = "info",
    help = "Print out information about the connected Redis server")
  parser.add_option("--no-load-balance",
    action = "store_false",
    default = "True",
    dest = "load_balance",
    help = "By default, this utility will enable software load balancing by querying redis servers within a core at random.  The working set is duplicated.  If you enable this flag, all redis servers in a core will be queried which will return dupliate results.  This is really only useful for printing server statistics using the --info flag.") 
  parser.add_option("--compare",
    action = "store",
    dest = "compare",
    help = "Compare two objects in the cache for differences")
  parser.add_option("--compare-all",
    action = "store_true",
    dest = "compare_all",
    help = "Compare all objects in the cache for differences, sorted by md5sum. The most popular item is diffed against the less popular entries.")
  parser.add_option("--hostlist",
    action = "store_true",
    dest = "hostlist",
    help = "When using --compare-all, display the list of machines that matched the various keys being used to compare.")

  (options,args) = parser.parse_args()
  validate_cli_args()

###############################################################################################################################################
  if (options.search or options.info or options.list_files) and not options.compare and not options.compare_all:
    try:
      redisResults = CacheExtractor.CacheExtractor(verbose = options.verbose,
						scope = options.scope,
						site = options.site,
						range_servers = options.range_servers,
						return_randomized_servers = options.load_balance,
						list_files = options.list_files,
						prefix_hostnames = options.prefix_hostnames,
						md5sum = options.md5sum,
						stat = options.stat,
						wordcount = options.wordcount,
						contents = options.contents,
						range_query = options.range_query,
						search_string = options.search)
    except Exception, e:
      print e
      sys.exit(1)
  
    if not redisResults._gold and not options.info:
      print "No objects were found with the above search query."
      sys.exit(1)

    # option 1.  This is --info
    if options.info:
      redisResults.print_redis_server_information()
      sys.exit(0)

    for key in sorted(redisResults._gold.iterkeys()):
      host, file = key.split('#')

      if not redisResults._gold[key]:
        # option 2. This is --search without --contents, --md5sum, --stat, --wordcount
        # option 3. This is --list-files
        if (options.search and
	   options.contents is None and
	   options.md5sum is None and
	   options.stat is None and
	   options.wordcount is None) or options.list_files:
          print key
          continue

      # option 4. This is --search with --contents
      # option 5. This is --search with --md5sum
      # option 6. This is --search with --stat
      # option 7. This is --search with --wordcount
      if options.search and (options.contents or options.md5sum or options.stat or options.wordcount):
        if options.prefix_hostnames:
          beginnning_of_line = re.compile("^")
          keystring = key.ljust(50)
          if redisResults._gold[key]:
            for line in redisResults._gold[key].splitlines():
              print beginnning_of_line.sub(keystring + "\t", line)
        else:
          if redisResults._gold[key]:
            print redisResults._gold[key].strip()
    sys.exit(0)

###############################################################################################################################################
  # option 8, This is --search with --compare
  if options.search and options.compare:
    if not options.contents and not options.stat and not options.md5sum and not options.wordcount:
      options.contents = True
    # If using --compare, the --range-query option must be used on the compareResults object to return multiple results, not 
    # the redisResults object.  The redisResults object must return exactly one item.
    # Since we are directly modifying the object, we re-declare it here under this option so the intention is clear.
    try:
      redisResults = CacheExtractor.CacheExtractor(verbose = options.verbose,
						scope = options.scope,
						site = options.site,
						range_servers = options.range_servers,
						return_randomized_servers = options.load_balance,
						list_files = options.list_files,
						prefix_hostnames = options.prefix_hostnames,
						md5sum = options.md5sum,
						stat = options.stat,
						wordcount = options.wordcount,
						contents = options.contents,
						range_query = False,  # this is modified.  The range_query applies to the compareResults object.
						search_string = options.search)
    except Exception, e:
      print e
      sys.exit(1)

    if not redisResults._gold:
      print "No objects were found with the above search query."
      sys.exit(1)

    try:
      compareResults = CacheExtractor.CacheExtractor(verbose = options.verbose,
						scope = options.scope,
						site = options.site,
						range_servers = options.range_servers,
						return_randomized_servers = options.load_balance,
						list_files = options.list_files,
						prefix_hostnames = options.prefix_hostnames,
						md5sum = options.md5sum,
						stat = options.stat,
                                 		wordcount = options.wordcount,
						contents = options.contents,
						range_query = options.range_query,
						search_string = options.compare)
    except Exception, e:
      print "We found results with the --search string but did not find results with the --compare string. You should use --search to find a string that can be used with --compare to find valid results so we can actually compare data.  The --search option must return exactly one result.  The --compare option can return one or more results."
      sys.exit(1)

    if not compareResults._gold:
      print "No objects were found with the above compare query."
      sys.exit(1)

    sanatize_compare_inputs(options, redisResults, compareResults)
    for compare_key in sorted(compareResults._gold.iterkeys()):
      # There is only one item in redisResults._gold, but we need to extract it.  i.e. this iterator only executes once.
      for key in redisResults._gold.iterkeys():
        compare_two_extracted_objects(key, redisResults._gold[key], compare_key, compareResults._gold[compare_key])
    sys.exit(0)
###############################################################################################################################################
  # option 8, This is --compare-all
  if options.search and options.compare_all:
    try:
      redisResults = CacheExtractor.CacheExtractor(verbose = options.verbose,
						scope = options.scope,
						site = options.site,
						range_servers = options.range_servers,
						prefix_hostnames = options.prefix_hostnames,
						md5sum = True,
						range_query = options.range_query,
						search_string = options.search)
    except Exception, e:
      print e
      sys.exit(1)

    if not redisResults._gold:
      print "No objects were found with the above search query."
      sys.exit(1)

    hashpipe = {}
    binger = {}
    
    # First, for each key we found, count the number of times we saw each unique md5sum and build a list of the found keys
    for key in redisResults._gold.iterkeys():
      host, file = key.split('#')
      if redisResults._gold[key]:
        md5sum = redisResults._gold[key].strip()
        if hashpipe.get(md5sum):
          hashpipe[md5sum][0] += 1
          hashpipe[md5sum][1].append(host)
        else:
          hashpipe[md5sum] = []
          hashpipe[md5sum].append(1)  		# This is the count of md5sums
          hashpipe[md5sum].append(list()) 	# This is the list of keys with the matching md5sum
        
    # Now that we have a count of how many times we saw each hash, iterate over each unique md5sum and find an example key.
    for md5sum in hashpipe.iterkeys():
      for key in redisResults._gold.iterkeys():
        if redisResults._gold[key] == md5sum:
          break
      binger[key] = []
      binger[key].append(hashpipe[md5sum][0]) 	# This is the count of md5sums
      binger[key].append(md5sum)
      binger[key].append(hashpipe[md5sum][1])	# This is the list of keys with the matching md5sum

    # Now that we are ready to start comparing data, set --contents to true.
    if not options.contents and not options.stat and not options.md5sum and not options.wordcount:
      options.contents = True

    # binger is now a dictionary with each item being a key of a unique md5sum.  perform a CacheExtractor search and compare with its friends.
    # once we reach 1 item, it doesn't make sense to compare it against itself, so bail. 
    # If we start off with only 1 item, then everything is identical.
    if len(binger) == 1:
      first_key, (first_key_count, first_key_md5sum, first_key_hostlist) = binger.popitem()
      print "All machines with the key " + first_key + " had the same md5sum " + first_key_md5sum
      if options.hostlist:
        for host in first_key_hostlist:
          print host
      sys.exit(0)

    # Calculate how many actual comparisons will be executed.
    total_comparisons = 0
    for x in range(0, (len(binger) + 1)):
      total_comparisons = total_comparisons + (x -1)
    total_comparisons += 1
    
    attention_whore = "***********************************************************************************"
    print attention_whore.center(150)
    print attention_whore.center(150)
    print attention_whore.center(150)
    print "Comparison Summary: " + str(len(binger)) + " unique objects exist in the cache."
    print "A total of " + str(total_comparisons) + " comparisons will be executed below"
    for key in binger.iterkeys():
      (key_count, key_md5sum, key_hostlist) = binger[key]
      print "Unique sample object " + key + " with md5sum " + key_md5sum + " found " + str(key_count) + " times."
    print attention_whore.center(150)
    print attention_whore.center(150)
    print attention_whore.center(150)
    print "\n\n\n"

    while len(binger) > 1:
      first_key, (first_key_count, first_key_md5sum, first_key_hostlist) = binger.popitem()
      print attention_whore.center(150)
      print "Starting comparison of  object " + first_key
      print attention_whore.center(150)
      try:
        redisResults = CacheExtractor.CacheExtractor(verbose = options.verbose,
						scope = options.scope,
						site = options.site,
						range_servers = options.range_servers,
						return_randomized_servers = options.load_balance,
						list_files = options.list_files,
						prefix_hostnames = options.prefix_hostnames,
						md5sum = options.md5sum,
						stat = options.stat,
						wordcount = options.wordcount,
						contents = options.contents,
						range_query = options.range_query,
						search_string = first_key)  # This option modified to search for first_key
      except Exception, e:
        print e
        sys.exit(1)

      # Now that we have an item to compare with, iterate over the remaining unique items in binger.
      for compare_key in binger.iterkeys():
        compare_key_count = binger[compare_key][0]
        compare_key_md5sum = binger[compare_key][1]
        compare_key_hostlist = binger[compare_key][2]
        try:
          compareResults = CacheExtractor.CacheExtractor(verbose = options.verbose,
						scope = options.scope,
						site = options.site,
						range_servers = options.range_servers,
						return_randomized_servers = options.load_balance,
						list_files = options.list_files,
						prefix_hostnames = options.prefix_hostnames,
						md5sum = options.md5sum,
						stat = options.stat,
						wordcount = options.wordcount,
						contents = options.contents,
						range_query = options.range_query,
						search_string = compare_key)  # This option modified to search for first_key
        except Exception, e:
          print e
          sys.exit(1)

        print "Comparing sample object " + first_key + " with md5sum " + first_key_md5sum + " found " + str(first_key_count) + " times."
        if options.hostlist:
          print "Hostlist for the key " + first_key
          for key in first_key_hostlist:
            print key
        print "Comparing sample object " + compare_key + " with md5sum " + compare_key_md5sum + " found " + str(compare_key_count) + " times."
        if options.hostlist:
          print "Hostlist for the key " + compare_key
          for key in compare_key_hostlist:
            print key

        compare_two_extracted_objects(first_key, redisResults._gold[first_key], compare_key, compareResults._gold[compare_key])
      print attention_whore.center(150)
      print "Completion of comparison object " + first_key
      print attention_whore.center(150)
    sys.exit(0)
###############################################################################################################################################
