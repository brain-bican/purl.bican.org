#!/usr/bin/env python3
#
# Migrate PURL configuration
# from a [PURL.org](http://purl.org) XML file
# to a YAML configuration file.
# This script is helpful, but manual improvements are required!
#
# Given the project ID, this tool will generate several required fields,
# then read the PURL.org XML to generate a list of entries.
#
# Each PURL is configured in a `<purl>` element, like this:
#
#     <purl status="1">
#       <id>/obo/obi/branches/</id>
#       <type>partial</type>
#       <maintainers><uid>ALANRUTTENBERG</uid></maintainers>
#       <target>
#         <url>http://obi.svn.sourceforge.net/svnroot/obi/trunk/src/ontology/branches/</url>
#       </target>
#     </purl>
#
# The result will be a YAML entry like this:
#
#     entries:
#     - prefix: /branches/
#       replacement: http://obi.svn.sourceforge.net/svnroot/obi/trunk/src/ontology/branches/
#
# We use a SAX parser to efficiently read selected fields: id, type, url.
#
# PURLs with type "302" will be `exact` entries.
# PURLs with type "partial" will be `prefix` entries.
# To ensure that PURL.org behaviour is duplicated by default,
# the `exact` entries are output first,
# followed by `prefix` entries in descending order of `id` length.

import argparse
import re
import os
import sys
import xml.sax

# Accumulate entries in these global lists for later sorting.
exact = []
prefix = []

# Define two template strings.
header_template = '''# PURL configuration for http://purl.brain-bican.org%s

idspace: %s
base_url: %s

products:
- %s.owl: TODO
- %s.obo: TODO

term_browser: ontobee
example_terms:
- TODO

entries:
'''

entry_template = '''- %s: %s
  replacement: %s

'''


# Parse command line arguments,
# run the SAX parser on the XML file,
# and write results to the YAML file.
def main():
  parser = argparse.ArgumentParser(description='Migrate XML to YAML')
  parser.add_argument('idspace',
                      type=str,
                      help='the project IDSPACE, e.g. FOO')
  parser.add_argument('xml_file',
                      type=argparse.FileType('r'),
                      default=sys.stdin,
                      nargs='?',
                      help='read from the XML file (or STDIN)')
  parser.add_argument('yaml_file',
                      type=str,
                      nargs='?',
                      help='write to the YAML file (or STDOUT)')
  args = parser.parse_args()

  args.upper_idspace = args.idspace.upper()
  args.lower_idspace = args.idspace.lower()
  args.base_url = '/obo/' + args.lower_idspace
  if args.yaml_file is not None:
    try:
      args.yaml_file = open(args.yaml_file, 'w')
    except FileNotFoundError:
      os.makedirs(os.path.dirname(args.yaml_file))
      args.yaml_file = open(args.yaml_file, 'w')
  else:
    args.yaml_file = sys.stdout

  sax = xml.sax.make_parser()
  sax.setContentHandler(OCLCHandler(args))
  sax.parse(args.xml_file)

  entries = exact + sorted(prefix, key=lambda k: len(k['id']), reverse=True)
  if len(entries) == 0:
    raise ValueError('No entries to migrate')

  args.yaml_file.write(header_template %
                       (args.base_url, args.upper_idspace, args.base_url, args.lower_idspace,
                        args.lower_idspace))
  for entry in entries:
    args.yaml_file.write(entry_template %
                         (entry['rule'], entry['id'], entry['url']))

  args.yaml_file.close()


# Define a SAX ContentHandler class to match the XML format,
# and accumulate entry dictionaries into the global lists.
# See example above for XML format.
class OCLCHandler(xml.sax.ContentHandler):
  def __init__(self, args):
    # Initialize args with results of argparse.
    self.args = args
    self.count = 0
    self.content = ''
    self.entry = {}

  # If this is a new `<purl>` element, clear variables.
  # Always clear the content buffer.
  def startElement(self, name, attrs):
    self.content = ''
    if name == 'purl':
      self.count += 1
      self.entry = {}

  # Accumulate characters.
  def characters(self, content):
    self.content += content

  # Get the first value found for type, id, and url.
  # If this is the end of a `purl` element,
  # validate the entry dictionary,
  # then store it in one of the global lists.
  def endElement(self, name):
    if name in ('type', 'id', 'url'):
      if self.content.strip() == '':
        raise ValueError('Empty <%s> for <purl> %d' % (name, self.count))
      self.entry[name] = self.content.strip()

    elif name == 'purl':
      # The `<id>` in the XML must begin with the base_url,
      # but we remove this prefix from the YAML output.
      if 'id' not in self.entry:
        raise ValueError('No <id> for <purl> %d' % self.count)
      id_re = re.compile('^' + self.args.base_url, re.IGNORECASE)
      if not id_re.match(self.entry['id']):
        raise ValueError(
          'In <purl> %d the <id> "%s" does not begin with base_url "%s"'
          % (self.count, self.entry['id'], self.args.base_url))
      self.entry['id'] = id_re.sub('', self.entry['id'])

      if 'url' not in self.entry:
        raise ValueError('No <url> for <purl> %d' % self.count)
      if not re.match(r'^(https?|ftp)\:\/\/.+', self.entry['url']):
        raise ValueError(
          'In <purl> %d the <url> "%s" is not an absolute HTTP or FTP URL'
          % (self.count, self.entry['url']))

      if 'type' not in self.entry:
        raise ValueError('No <type> for <purl> %d' % self.count)
      elif self.entry['type'] == '302':
        self.entry['rule'] = 'exact'
        exact.append(self.entry)
      elif self.entry['type'] == 'partial':
        self.entry['rule'] = 'prefix'
        prefix.append(self.entry)
      else:
        raise ValueError('Unknown type "%s" for <purl> %d' %
                         (self.entry['type'], self.count))


if __name__ == "__main__":
    main()
