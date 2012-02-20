#! /usr/bin/python
"""

    NIPAP Command-line interface

    TODO
    ----

    Schema:
    add             done
    list            
    search          
    modify          done
    remove          done
    view            done
    format view

    Pool:
    add             done
    list            done
    format list     done
    modify          done
    add prefix
    remove prefix
    expand
    remove          done
    view            done

    Prefix:
    add
     - from pool    done
     - from prefix  done
     - specified    done
     - complete host
    list            done
    modify
    remove
    view            done


"""

import os
import sys
import re
import ConfigParser
sys.path.append('../pynipap')
import pynipap
from pynipap import Schema, Pool, Prefix, NipapError
from command import Command

# definitions
valid_countries = [ 'DE', 'EE', 'NL', 'SE', 'US' ] # test test, fill up! :)
valid_prefix_types = [ 'host', 'reservation', 'assignment' ]
valid_families = [ 'ipv4', 'ipv6' ]
valid_bools = [ 'true', 'false' ]
valid_priorities = [ 'low', 'medium', 'high' ]


# global vars
schema = None
cfg = None


def setup_connection(cfg):

    # build XML-RPC URI
    try:
        pynipap.xmlrpc_uri = "http://%(username)s:%(password)s@%(hostname)s:%(port)s" % {
                'username': cfg.get('global', 'username'),
                'password': cfg.get('global', 'password'),
                'hostname': cfg.get('global', 'hostname'),
                'port'    : cfg.get('global', 'port')
            }
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        print >> sys.stderr, "Please define the username, password, hostname and port in your .nipaprc under the section 'global'"
        sys.exit(1)

    ao = pynipap.AuthOptions({'authoritative_source': 'nipap'})



def get_schema():

    # if there is a schema set, return it
    if schema is not None:
        return schema

    # fetch default schema
    try:
        schema_name = cfg.get('global', 'schema')
    except ConfigParser.NoOptionError:
        print >> sys.stderr, "Please define the default schema in your .nipaprc"
        sys.exit(1)

    return Schema.list({ 'name': schema_name })[0]


def _str_to_bool(arg):

    if arg is None:
        return False

    if arg == 'true':
        return True
    elif arg == 'false':
        return False
    else:
        raise ValueError('Only values true and false permitted')


"""
    LIST FUNCTIONS
"""

def _expand_list_query(opts):

    # create list of query parts
    query_parts = []
    for key, val in opts.items():

        # standard case
        operator = 'regex_match'
        val1 = key
        val2 = "^%s" % val

        query_parts.append({
            'operator': operator,
            'val1': val1,
            'val2': val2
        })

    # Sum all query parts to one query
    query = {}
    if len(query_parts) > 0:
        query = query_parts[0]

    if len(query_parts) > 1:
        for query_part in query_parts[1:]:
            query = {
                'operator': 'and',
                'val1': query_part,
                'val2': query
            }

    return query


def list_pool(arg, opts):
    """ List pools matching a search criteria
    """

    s = get_schema()

    query = _expand_list_query(opts)
    res = Pool.search(s, query)
    if len(res['result']) > 0:
        print "%-20s%-40s%-15s%-8s" % ("Name", "Description", "Default type", "4 / 6")
        print "-----------------------------------------------------------------------------------"
    else:
        print "No matching pools found"

    for p in res['result']:
        if len(p.description) > 38:
            desc = p.description[0:34] + "..."
        else:
            desc = p.description
        print "%-20s%-40s%-15s%-2s / %-3s" % (p.name, desc, p.default_type, str(p.ipv4_default_prefix_length), str(p.ipv6_default_prefix_length))



def list_schema(arg, opts):
    """ List schemas matching a search criteria
    """

    query = _expand_list_query(opts)
    res = Schema.search(query)
    if len(res['result']) > 0:
        print "Name Description VRF"
    else:
        print "No matching schemas found."

    for s in res['result']:
        print "%s %s %s" % (s.name, s.description, s.vrf)



def list_prefix(arg, opts):
    """ List prefixes matching 'arg'
    """

    s = get_schema()

    res = Prefix.smart_search(s, arg, { 'parents_depth': -1, 'max_result': 1200 })
    if len(res['result']) == 0:
        print "No addresses matching '%s' found." % arg
        return

    for p in res['result']:
        if p.display == False:
            continue

        try:
            print "%-30s%-3s%-20s%-15s%-40s" % ("".join("  " for i in range(p.indent)) + p.display_prefix, p.type[0].upper(), p.node, p.order_id, p.description)
        except UnicodeEncodeError, e:
            print "\nCrazy encoding for prefix %s\n" % p.prefix



"""
    ADD FUNCTIONS
"""

def add_prefix(arg, opts):
    """ Add prefix to NIPAP
    """

    s = get_schema()

    p = Prefix()
    p.schema = s
    p.prefix = opts.get('prefix')
    p.type = opts.get('type')
    p.descripton = opts.get('description')
    p.node = opts.get('node')
    p.country = opts.get('country')
    p.order_id = opts.get('order_id')
    p.alarm_priority = opts.get('alarm_priority')
    p.comment = opts.get('comment')
    p.monitor = _str_to_bool(opts.get('monitor'))

    args = {}
    if 'from-pool' in opts:
        res = Pool.list(s, { 'name': opts['from-pool'] })
        if len(res) == 0:
            print >> sys.stderr, "No pool named %s found." % opts['from-pool']
            sys.exit(1)

        args['from-pool'] = res[0]
        
    if 'from-prefix' in opts:
        args['from-prefix'] = [ opts['from-prefix'], ]

    if 'prefix-length' in opts:
        args['prefix_length'] = int(opts['prefix-length'])

    if 'family' in opts:
        family = opts['family']
        if opts['family'] == 'ipv4':
            family = 4
        elif opts['family'] == 'ipv6':
            family = 6

        args['family'] = family


    try:
        p.save(args)
    except NipapError, e:
        print >> sys.stderr, "Could not add prefix to NIPAP: %s" % e.message
        sys.exit(1)

    print "Prefix %s added." % p.display_prefix



def add_schema(arg, opts):
    """ Add schema to NIPAP
    """

    s = Schema()
    s.name = opts.get('name')
    s.description = opts.get('description')
    s.vrf = opts.get('vrf')

    try:
        s.save()
    except pynipap.NipapError, e:
        print >> sys.stderr, "Could not add schema to NIPAP: %s" % e.message
        sys.exit(1)

    print "Added schema %s with id %d" % (s.name, s.id)



def add_pool(arg, opts):
    """ Add a pool.
    """

    p = Pool()
    p.schema = get_schema()
    p.name = opts.get('name')
    p.description = opts.get('description')
    p.default_type = opts.get('default_type')
    p.ipv4_default_prefix_length = opts.get('ipv4_default_prefix_length')
    p.ipv6_default_prefix_length = opts.get('ipv6_default_prefix_length')

    try:
        p.save()
    except pynipap.NipapError, e:
        print >> sys.stderr, "Could not add pool to NIPAP: %s" % e.message
        sys.exit(1)

    print "Pool %s created with id %s" % (p.name, p.id)


"""
    VIEW FUNCTIONS
"""
def view_schema(arg, opts):
    """ View a single schema
    """

    res = Schema.list({ 'name': arg })
    if len(res) < 1:
        print >> sys.stderr, "No schema with name %s found." % arg
        sys.exit(1)

    s = res[0]

    print "Name: %s\nDescription: %s\nVRF: %s" % (s.name, s.description, s.vrf)


def view_pool(arg, opts):
    """ View a single pool
    """

    s = get_schema()

    res = Pool.list(s, { 'name': arg })

    if len(res) == 0:
        print "No pool named %s found." % arg
        return

    p = res[0]
    print  "-- Pool "
    print "  %-15s : %s" % ("Name", p.name)
    print "  %-15s : %s" % ("Description", p.description)
    print "  %-15s : %s" % ("Default type", p.default_type)
    print "  %-15s : %s / %s" % ("Preflen (v4/v6)", str(p.ipv4_default_prefix_length), str(p.ipv6_default_prefix_length))
    print "\n-- Prefixes in pool"

    res = Prefix.list(s, { 'pool': p.id})
    for pref in res:
        print "  %s" % pref.display_prefix



def view_prefix(arg, opts):
    """ View a single prefix.
    """

    s = get_schema()

    res = Prefix.search(s, { 'operator': 'equals', 'val1': 'prefix', 'val2': arg }, {})

    if len(res['result']) == 0:
        print "Address %s not found." % arg
        return

    p = res['result'][0]
    print  "-- Address "
    print "  %-15s : %s" % ("Prefix", p.prefix)
    print "  %-15s : %s" % ("Display prefix", p.display_prefix)
    print "  %-15s : %s" % ("Type", p.type)
    print "  %-15s : IPv%s" % ("Family", p.family)
    print "  %-15s : %s" % ("Description", p.description)
    print "  %-15s : %s" % ("Node", p.node)
    print "  %-15s : %s" % ("Order", p.order_id)
    print "  %-15s : %s" % ("Alarm priority", p.alarm_priority)
    print "  %-15s : %s" % ("Monitor", p.monitor)
    print "-- Comment"
    print p.comment




"""
    REMOVE FUNCTIONS
"""

def remove_schema(arg, opts):

    res = Schema.list({ 'name': arg })
    if len(res) < 1:
        print >> sys.stderr, "No schema with name %s found." % arg
        sys.exit(1)

    s = res[0]

    print "Name: %s\nDescription: %s\nVRF: %s" % (s.name, s.description, s.vrf)
    print "\nWARNING: THIS WILL REMOVE THE SCHEMA INCLUDING ALL IT'S ADDRESSES"
    res = raw_input("Do you really want to remove the schema %s? [y/n]: " % s.name)

    if res == 'y':
        s.remove()
        print "Schema %s removed." % s.name
    else:
        print "Operation canceled."


def remove_pool(arg, opts):

    s = get_schema()
    res = Pool.list(s, { 'name': arg })
    if len(res) < 1:
        print >> sys.stderr, "No pool with name %s found." % arg
        sys.exit(1)

    p = res[0]

    res = raw_input("Do you really want to remove the pool %s? [y/n]: " % p.name)

    if res == 'y':
        p.remove()
        print "Pool %s removed." % p.name
    else:
        print "Operation canceled."


"""
    MODIFY FUNCTIONS
"""

def modify_schema(arg, opts):
    """ Modify a schema with the options set in opts
    """

    res = Schema.list({ 'name': arg })
    if len(res) < 1:
        print >> sys.stderr, "No schema with name %s found." % arg
        sys.exit(1)

    s = res[0]

    if 'name' in opts:
        s.name = opts['name']
    if 'vrf' in opts:
        s.vrf = opts['vrf']
    if 'description' in opts:
        s.description = opts['description']

    s.save()

    print "Schema %s saved." % s.name



def modify_pool(arg, opts):
    """ Modify a pool with the options set in opts
    """

    s = get_schema()
    res = Pool.list(s, { 'name': arg })
    if len(res) < 1:
        print >> sys.stderr, "No pool with name %s found." % arg
        sys.exit(1)

    p = res[0]

    if 'name' in opts:
        p.name = opts['name']
    if 'description' in opts:
        p.description = opts['description']
    if 'default_type' in opts:
        p.default_type = opts['default_type']
    if 'ipv4_default_prefix_length' in opts:
        p.ipv4_default_prefix_length = opts['ipv4_default_prefix_length']
    if 'ipv6_default_prefix_length' in opts:
        p.ipv6_default_prefix_length = opts['ipv6_default_prefix_length']

    p.save()

    print "Pool %s saved." % p.name



def modify_prefix(arg, opts):
    """ Modify the prefix 'arg' with the options 'opts'
    """

    s = get_schema()

    res = Prefix.list(s, { 'prefix': arg })
    if len(res) == 0:
        print >> sys.stderr, "Prefix %s not found." % arg

    p = res[0]

    if 'description' in opts:
        p.description = opts['description']
    if 'comment' in opts:
        p.comment = opts['comment']
    if 'node' in opts:
        p.node = opts['node']
    if 'type' in opts:
        p.type = opts['type']
    if 'country' in opts:
        p.country = opts['country']
    if 'order_id' in opts:
        p.order_id = opts['order_id']
    if 'alarm_priority' in opts:
        p.alarm_priority = opts['alarm_priority']
    if 'monitor' in opts:
        p.monitor = _str_to_bool(opts['monitor'])

    try:
        p.save()
    except NipapError, e:
        print >> sys.stderr, "Could not save prefix changes: %s" % e.message
        sys.exit(1)

    print "Prefix %s saved." % p.display_prefix



"""
    COMPLETION FUNCTIONS
"""

def _complete_string(key, haystack):

    if len(key) == 0:
        return haystack

    match = []
    for straw in haystack:
        if re.match(key, straw):
            match.append(straw)
    return match



def complete_bool(arg):
    return _complete_string(arg, valid_bools)

    

def complete_country(arg):
    return _complete_string(arv, valid_countries)



def complete_family(arg):
    return _complete_string(arg, valid_families)



def complete_prefix_type(arg):
    return _complete_string(arg, valid_prefix_types)



def complete_priority(arg):
    return _complete_string(arg, valid_priorities)



def complete_pool_name(arg):

    s = get_schema()
    search_string = '^'
    if arg is not None:
        search_string += arg
    res = Pool.search(s, {
        'operator': 'regex_match',
        'val1': 'name',
        'val2': search_string
    })
    ret = []
    for p in res['result']:
        ret.append(p.name)

    return ret



def complete_schema_name(arg):

    search_string = ''
    if arg is not None:
        search_string = '^%s' % arg

    res = Schema.search({
        'operator': 'regex_match',
        'val1': 'name',
        'val2':  search_string
        })
    ret = []
    for schema in res['result']:
        ret.append(schema.name)

    return ret



"""
    VALIDATION FUNCTIONS
"""
def validate_bool(arg):
    return arg in valid_bools



def validate_country(arg):
    return arg in valid_countries



def validate_family(arg):
    return arg in valid_families



def validate_prefix_type(arg):
    return arg in valid_prefix_types



def validate_priority(arg):
    return arg in valid_priorities



def validate_schema_name(arg):

    res = Schema.search({
        'operator': 'equals',
        'val1': 'name',
        'val2': arg
        })

    return len(res['result']) == 1



def validate_pool_name(arg):
    """ Validate if there is a pool with name 'arg'
    """

    s = get_schema()

    res = Pool.search(s, {
        'operator': 'equals',
        'val1': 'name',
        'val2': arg
        })

    return len(res['result']) == 1


cmds = {
    'params': {
        'address': {
            'type': 'command',
            'params': {

                # add
                'add': {
                    'type': 'command',
                    'exec': add_prefix,
                    'params': {
                        'comment': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                            }
                        },
                        'country': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'complete': complete_country,
                                'validator': validate_country
                            }
                        },
                        'description': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                            }
                        },
                        'family': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'complete': complete_family,
                                'validator': validate_family
                            }
                        },
                        'type': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'description': 'Prefix type: reservation | assignment | host',
                                'content_type': unicode,
                                'complete': complete_prefix_type,
                                'validator': validate_prefix_type
                            }
                        },
                        'from-pool': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'complete': complete_pool_name,
                                'validator': validate_pool_name,
                            }
                        },
                        'from-prefix': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                            }
                        },
                        'node': {
                            'type': 'option',
                            'content_type': unicode,
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
#                                'complete': complete_node,
#                                'validator': validate_node
                            }
                        },
                        'order': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                            }
                        },
                        'prefix': {
                            'type': 'option',
                            'content_type': unicode,
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                            }
                        },
                        'prefix-length': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': int
                            }
                        },
                        'monitor': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'complete': complete_bool,
                                'validator': validate_bool
                            }
                        },
                        'alarm_priority': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'complete': complete_priority,
                                'validator': validate_priority
                            }
                        }
                    },
                },

                # list
                'list': {
                    'type': 'command',
                    'exec': list_prefix,
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Prefix',
                    },
                },

                # modify
                'modify': {
                    'type': 'command',
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Prefix to edit',
                    },
                    'params': {
                        'set': {
                            'type': 'command',
                            'exec': modify_prefix,
                            'params': {
                                'comment': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                    }
                                },
                                'country': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'complete': complete_country,
                                        'validator': validate_country
                                    }
                                },
                                'description': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                    }
                                },
                                'family': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'complete': complete_family,
                                        'validator': validate_family
                                    }
                                },
                                'type': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'description': 'Prefix type: reservation | assignment | host',
                                        'content_type': unicode,
                                        'complete': complete_prefix_type,
                                        'validator': validate_prefix_type
                                    }
                                },
                                'node': {
                                    'type': 'option',
                                    'content_type': unicode,
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
        #                                'complete': complete_node,
        #                                'validator': validate_node
                                    }
                                },
                                'order': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                    }
                                },
                                'monitor': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'complete': complete_bool,
                                        'validator': validate_bool
                                    }
                                },
                                'alarm_priority': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'complete': complete_priority,
                                        'validator': validate_priority
                                    }
                                }
                            }
                        }
                    }
                },

                # remove
                'remove': {
                    'type': 'command',
                    'argument': {
                        'content_type': unicode,
                        'description': 'Address to remove'
                    }
                },

                # view
                'view': {
                    'type': 'command',
                    'exec': view_prefix,
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Address to view'
                    }
                }
            }
        },

        # schema commands
        'schema': {
            'type': 'command',
            'params': {
                'add': {
                    'type': 'command',
                    'exec': add_schema,
                    'params': {
                        'vrf': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'description': 'VRF which the schema is mapped to'
                            }
                        },
                        'name': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'description': 'Schema name',
                            }

                        },
                        'description': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'description': 'VRF which the schema is mapped to'
                            }
                        }
                    }
                },
                'list': {
                    'type': 'command',
                    'exec': list_schema,
#                    'argument': {
#                        'type': 'value',
#                        'content_type': unicode,
#                        'descripton': 'Schema search string'
#                    },
                    'params': {
                        'vrf': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'description': 'VRF which the schema is mapped to'
                            }
                        },
                        'name': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'description': 'Schema name',
                                'complete': complete_schema_name,
                                'validator': validate_schema_name
                            }

                        },
                        'description': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'description': 'VRF which the schema is mapped to'
                            }
                        }
                    }
                },
                'view': {
                    'exec': view_schema,
                    'type': 'command',
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Schema name',
                        'complete': complete_schema_name,
                        'validator': validate_schema_name
                    }
                },
                'remove': {
                    'exec': remove_schema,
                    'type': 'command',
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Schema name',
                        'complete': complete_schema_name,
                        'validator': validate_schema_name
                    }
                },
                'modify': {
                    'type': 'command',
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Schema name',
                        'complete': complete_schema_name,
                        'validator': validate_schema_name
                    },
                    'params': {
                        'set': {
                            'type': 'command',
                            'exec': modify_schema,
                            'params': {
                                'vrf': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'description': 'VRF which the schema is mapped to'
                                    }
                                },
                                'name': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'description': 'Schema name',
                                    }

                                },
                                'description': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'description': 'VRF which the schema is mapped to'
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },

        # pool commands
        'pool': {
            'type': 'command',
            'params': {

                # add
                'add': {
                    'type': 'command',
                    'exec': add_pool,
                    'params': {
                        'default_type': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'descripton': 'Default prefix type: reservation | assignment | host',
                                'complete': complete_prefix_type,
                                'validator': validate_prefix_type
                            }
                        },
                        'name': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'descripton': 'Name of the pool'
                            }
                        },
                        'description': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'descripton': 'A short description of the pool'
                            }
                        },
                        'ipv4_default_prefix_length': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': int,
                                'descripton': 'Default IPv4 prefix length'
                            }
                        },
                        'ipv6_default_prefix_length': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': int,
                                'descripton': 'Default IPv6 prefix length'
                            }
                        }
                    }
                },

                # list
                'list': {
                    'type': 'command',
                    'exec': list_pool,
                    'params': {
                        'default_type': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'descripton': 'Default prefix type: reservation | assignment | host',
                                'complete': complete_prefix_type,
                                'validator': validate_prefix_type
                            }
                        },
                        'name': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'descripton': 'Name of the pool'
                            }
                        },
                        'description': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': unicode,
                                'descripton': 'A short description of the pool'
                            }
                        },
                        'ipv4_default_prefix_length': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': int,
                                'descripton': 'Default IPv4 prefix length'
                            }
                        },
                        'ipv6_default_prefix_length': {
                            'type': 'option',
                            'argument': {
                                'type': 'value',
                                'content_type': int,
                                'descripton': 'Default IPv6 prefix length'
                            }
                        }
                    }
                },

                # remove
                'remove': {
                    'type': 'command',
                    'exec': remove_pool,
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Pool name',
                        'complete': complete_pool_name,
                        'validator': validate_pool_name
                    }
                },

                # modify
                'modify': {
                    'type': 'command',
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Pool name',
                        'complete': complete_pool_name,
                        'validator': validate_pool_name
                    },
                    'params': {
                        'set': {
                            'type': 'command',
                            'exec': modify_pool,
                            'params': {
                                'default_type': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'descripton': 'Default prefix type: reservation | assignment | host',
                                        'complete': complete_prefix_type,
                                        'validator': validate_prefix_type
                                    }
                                },
                                'name': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'descripton': 'Name of the pool'
                                    }
                                },
                                'description': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': unicode,
                                        'descripton': 'A short description of the pool'
                                    }
                                },
                                'ipv4_default_prefix_length': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': int,
                                        'descripton': 'Default IPv4 prefix length'
                                    }
                                },
                                'ipv6_default_prefix_length': {
                                    'type': 'option',
                                    'argument': {
                                        'type': 'value',
                                        'content_type': int,
                                        'descripton': 'Default IPv6 prefix length'
                                    }
                                }
                            }
                        }
                    }

                },

                # view
                'view': {
                    'exec': view_pool,
                    'type': 'command',
                    'argument': {
                        'type': 'value',
                        'content_type': unicode,
                        'description': 'Pool name',
                        'complete': complete_pool_name,
                        'validator': validate_pool_name
                    }

                }
            }
        }
    }
}

# read configuration
cfg = ConfigParser.ConfigParser()
cfg.read(os.path.expanduser('~/.nipaprc'))

setup_connection(cfg)

if __name__ == '__main__':

    try:
        cmd = Command(cmds, sys.argv[1::])
    except ValueError, e:
        print >> sys.stderr, "Error: %s" % e.message
        sys.exit(1)

    # execute command
    if cmd.exe is None:
        print "Incomplete command specified"
        print "valid completions: %s" % cmd.get_complete_string()
        sys.exit(1)

    cmd.exe(cmd.arg, cmd.exe_options)

