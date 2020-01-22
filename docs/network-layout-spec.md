# Test Network Layout Specification

In attempting to configure and deploy Tendermint test networks across one or
more regions in AWS, it has become apparent that there is a need for some form
of specification language to describe such a layout. Once we have a standardized
specification language, it should be relatively easy to develop a small tool to
parse it, and using all of the scripts in this repository, deploy this network.

## Configuration

This is an example configuration file to illustrate arbitrary usage of the
proposed tool:

```yaml
# A global identifier to apply across the entire test network. Will be added
# to the `Group` tags on all created AWS resources. This identifier is included
# in metrics submitted from the Tendermint nodes in this network.
# This is also used as the Tendermint network chain ID.
id: testnet_abcd

# This parameter goes in the genesis file: `consensus_params.block.max_bytes`.
# Numeric format expected here.
# Expected range: [1, 21504].
block_max_kb: 100

# Configuration relating to monitoring of the Tendermint network nodes. Right
# now, the idea is to support SignalFX and/or InfluxDB. At least one of the two
# must be configured.
monitoring:
  # Any SignalFX-related configuration parameters will go here.
  signalfx:
    enabled: no
    api_token: $SIGNALFX_API_TOKEN
    realm: $SIGNALFX_REALM

  influxdb:
    enabled: yes
    # Set to `yes` to deploy the Grafana/InfluxDB monitoring server. If set to
    # `no`, you will need to supply InfluxDB details to which to send the
    # metrics.
    deploy: yes

    # Where do you want to deploy the monitoring server?
    region: us-east-1

    # If deploy is set to `no`, the InfluxDB URL is required.
    #url: https://your-own-influxdb-host:8086

    # These options can't be changed at the moment.
    #database: tendermint
    #username: tendermint

    # What password should we use for InfluxDB? If not specified, a strong
    # password will automatically be generated.
    password: $INFLUXDB_PASSWORD

# Allows you to specify different configurations of your ABCI application, each
# with its own unique identifier. You can leave this section out completely if
# you're going to be using one of the built-in apps (like the kvstore), or if
# the binary you're deploying uses Tendermint as a library.
abci:
  # Each ABCI application configuration lists 3 Ansible playbooks: one for
  # deploying your ABCI app, one for starting it, and one for stopping it.
  # Each configuration allows for specifying extra Ansible variables using the
  # extra_vars parameter. You can specify any number of variables here and they
  # will be passed into your playbook during its execution.
  myabciapp:
    deploy:
      playbook: ./myabciapp/deploy.yaml
      extra_vars:
        somevar: somevalue
        othervar: 1234
    start:
      playbook: ./myabciapp/start.yaml
    stop:
      playbook: ./myabciapp/stop.yaml

# The entry node_group_templates is not actually parsed - what's more important
# here is to note that PyYAML supports YAML anchors and aliases, which
# allow you to define templates in your YAML files.
node_group_templates:
  validator: &validator_template
    # If you want to deploy an official release of Tendermint, just specify
    # a version number here and its binary will be deployed from GitHub.
    binary: v0.31.7

    # What's the initial state of the Tendermint service? Can be "started" or
    # "stopped".
    service_state: started

    # Leaving this out assumes you're either using a built-in ABCI
    # application (like the kvstore) or your binary is built using Tendermint
    # as a library.
    abci: myabciapp

    # Are these nodes to be validators? (Default: yes)
    validators: yes

    # Are these nodes' details to be included in the `genesis.json` file?
    # (Default: yes)
    in_genesis: yes

    # Where to find the configuration file to use as a template for
    # generating configuration for all of the nodes in this sub-network.
    config_template: ./my-validators-config.toml

    # The group name(s) for nodes to consider as seeds
    use_seeds:
      - my_seeds

    # To prepopulate persistent peers' addresses, specify a list of group
    # names here. Can specify this group's own name here.
    #persistent_peers:
    #  - my_validators

# A mapping of named sub-groups of nodes within the desired test network
# resource group. All group names (e.g. `my_validators`, `my_seeds`, etc.) are
# totally arbitrary. You can have as many groups with different identifiers as
# you want.
node_groups:
  - my_validators:
      # We support YAML anchors and aliases, which effectively allow for
      # templating within the YAML file.
      <<: *validator_template

      # Where to deploy nodes for this group. Note that nodes are numbered
      # according to the order in which the regions appear here.
      regions:
        - us_east_1: 2    # my_validators[0], my_validators[1]
        - us_east_2: 1    # my_validators[2]
        - us_west_1: 3    # my_validators[3], my_validators[4], my_validators[5]

  - my_seeds:
      binary: v0.31.7
      # We don't want our seed nodes to be validators
      validators: no
      service_state: started
      # Be sure to set seed_mode = true in this configuration template
      config_template: ./seednode-config.toml
      # Where to deploy seed nodes for this group
      regions:
        - us_east_1: 1    # my_seeds[0]
        - us_west_1: 1    # my_seeds[1]

  - late_joiner_validators:
      # Derives from validator_template
      <<: *validator_template

      # If you want to deploy a custom Tendermint binary, specify its path
      # instead of an official release version. This overrides the value 
      # provided in the validator_template object.
      binary: /path/to/local/tendermint

      # We don't want these nodes to be included from the beginning. You will
      # have to add them to the network later manually/programmatically.
      in_genesis: no

      # The nodes should not be started automatically (assumes that you will
      # start the Tendermint services manually at a later stage)
      service_state: stopped
      config_template: ./late-joiners-config.toml
      regions:
        - us_east_1: 2   # late_joiner_validators[0],late_joiner_validators[1]
  
  - late_joiner_non_validators:
      binary: /path/to/local/tendermint
      validators: no
      in_genesis: no
      service_state: stopped
      config_template: ./late-joiners-config.toml
      use_seeds:
        - my_seeds
      regions:
        - us_west_1: 2   # late_joiner_non_validators[0],late_joiner_non_validators[1]

load_tests:
  - load0:
      # In future, `tm-load-test` will be supported. This will influence all of
      # the following parameters.
      method: tm-bench

      # The number of VMs (running tm-bench) to start
      client_nodes: 1

      # A list of targets for this load test
      targets:
        # Can specify an entire group to connect to all endpoints
        - my_validators
        # Can specify a single node within a group
        - late_joiner_validators[0]
      
      # The number of seconds for which to run the load test
      time: 120
      broadcast_tx_method: async
      connections: 1
      # The number of transactions per second to generate
      rate: 1000
      # The number of bytes to generate per transaction
      size: 250
```

NOTES:
1. The configuration file here needs to allow for easy environment variable
   interpolation. The BASH convention is probably best, e.g. `"$MYVAR"`.

## Interaction
In order to be easy to use, the test network layout tool would have to
facilitate:

1. Deployment of the network
2. Destruction of the network
3. Starting/stopping of individual Tendermint nodes
4. Start/stop load tests

For example, one should simply be able to run something like:

```bash
# By default, the tool should look for a file called `tmtestnet.yaml` or
# in the current folder. Override with --config parameter.

# Deploy the network (creating all AWS resources)
tmtestnet network deploy

# Destroy the entire network (deleting all AWS resources)
tmtestnet network destroy
# Destroy the entire Tendermint network, but keep the monitoring service (if
# deployed)
tmtestnet network destroy --keep-monitoring

# Start specific node group(s)
tmtestnet network start late_joiner_validators
# Start specific node(s)
tmtestnet network start late_joiner_validators[0] late_joiner_non_validators[0]

# Stop specific node group(s)
tmtestnet network stop late_joiner_validators late_joiner_non_validators
# Stop specific node(s)
tmtestnet network stop late_joiner_validators[0]

# Start load test
tmtestnet loadtest start load0

# Stop load test (destroy AWS resources)
tmtestnet loadtest stop
```
