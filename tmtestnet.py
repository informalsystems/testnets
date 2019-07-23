#!/usr/bin/env python3
"""
Test network deployment and management utility script for Tendermint
(https://tendermint.com).
"""

import argparse
import os
import os.path
import string
import sys
import re
import logging
import subprocess
import shlex
import time
import hashlib
from typing import OrderedDict as OrderedDictType, List, Dict, Set
from collections import namedtuple, OrderedDict
from copy import copy, deepcopy
import zipfile
import shutil
import pwd
import json
import datetime
import base64
import tempfile

import yaml
import colorlog
import requests
import toml
import pytz


# The default logger is pretty plain and boring
logger = logging.getLogger("")


def main():
    default_aws_keypair_name = get_current_user()
    default_ec2_private_key = os.path.expanduser("~/.ssh/ec2-user.pem")

    parser = argparse.ArgumentParser(
        description="Test network deployment and management utility script for Tendermint (https://tendermint.com)",
    )
    parser.add_argument(
        "-c", "--config", 
        default="./tmtestnet.yaml",
        help="The path to the configuration file to use (default: ./tmtestnet.yaml)"
    )
    parser.add_argument(
        "--aws-keypair-name",
        default=default_aws_keypair_name,
        help="The name of the AWS keypair you need to use to interact with AWS (defaults to your current username)",
    )
    parser.add_argument(
        "--ec2-private-key",
        default=default_ec2_private_key,
        help="The path to the private key that corresponds to your AWS keypair (default: ~/.ssh/ec2-user.pem)",
    )
    parser.add_argument(
        "--fail-on-missing-envvars",
        action="store_true",
        default=False,
        help="Causes the script to fail entirely if an environment variable used in the config file is not set (default behaviour will just insert an empty value)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Increase output verbosity",
    )
    subparsers = parser.add_subparsers(
        required=True,
        dest="command",
        help="The tmtestnet command to execute",
    )

    # network
    parser_network = subparsers.add_parser(
        "network", 
        help="Network-related functionality",
    )
    subparsers_network = parser_network.add_subparsers(
        required=True,
        dest="subcommand",
        help="The network-related command to execute",
    )

    # network deploy
    parser_network_deploy = subparsers_network.add_parser(
        "deploy", 
        help="Deploy a network according to its configuration file",
    )
    parser_network_deploy.add_argument(
        "--keep-existing-tendermint-config",
        action="store_true",
        help="If this flag is specified and configuration is already present for a particular node group, it will not be overwritten/regenerated",
    )

    # network destroy
    parser_network_destroy = subparsers_network.add_parser(
        "destroy", 
        help="Destroy a deployed network",
    )

    # network start
    parser_network_start = subparsers_network.add_parser(
        "start", 
        help="Start one or more node(s) or node group(s)",
    )
    parser_network_start.add_argument(
        "node_or_group_ids",
        metavar="node_or_group_id",
        nargs="*",
        help="Zero or more node or group IDs of network node(s) to start. If this is not supplied, all nodes will be started."
    )
    parser_network_start.add_argument(
        "--no-fail-on-missing",
        default=False,
        action="store_true",
        help="By default, this command fails if a group/node reference has not yet been deployed. Specifying this flag will just skip that group/node instead.",
    )

    # network stop
    parser_network_stop = subparsers_network.add_parser(
        "stop", 
        help="Stop one or more node(s) or node group(s)",
    )
    parser_network_stop.add_argument(
        "node_or_group_ids",
        metavar="node_or_group_id",
        nargs="*",
        help="Zero or more node or group IDs of network node(s) to stop. If this is not supplied, all nodes will be stopped."
    )
    parser_network_stop.add_argument(
        "--no-fail-on-missing",
        default=False,
        action="store_true",
        help="By default, this command fails if a group/node reference has not yet been deployed. Specifying this flag will just skip that group/node instead.",
    )

    # network fetch_logs
    parser_network_fetch_logs = subparsers_network.add_parser(
        "fetch_logs",
        help="Fetch the logs for one or more node(s) or node group(s). " +
            "Note that this stops any running service instances on the target " +
            "nodes prior to fetching the logs, and then restarts those instances " +
            "that were running previously.",
    )
    parser_network_fetch_logs.add_argument(
        "output_path",
        help="Where to store all desired nodes' logs."
    )
    parser_network_fetch_logs.add_argument(
        "node_or_group_ids",
        metavar="node_or_group_id",
        nargs="*",
        help="Zero or more node or group IDs of network node(s). If this is not supplied, all nodes' logs will be fetched."
    )

    # loadtest
    parser_loadtest = subparsers.add_parser(
        "loadtest", 
        help="Load testing-related functionality",
    )
    subparsers_loadtest = parser_loadtest.add_subparsers(
        required=True,
        dest="subcommand",
        help="The load testing-related sub-command to execute",
    )

    # loadtest start <name>
    parser_loadtest_start = subparsers_loadtest.add_parser("start", help="Start a specific load test")
    parser_loadtest_start.add_argument("name", help="The name of the load test to start")

    args = parser.parse_args()

    configure_logging(verbose=args.verbose)
    # Allow for interpolation of environment variables within YAML files
    configure_env_var_yaml_loading(fail_on_missing=args.fail_on_missing_envvars)

    kwargs = {
        "aws_keypair_name": os.environ.get("AWS_KEYPAIR_NAME", getattr(args, "aws_keypair_name", default_aws_keypair_name)),
        "ec2_private_key_path": os.environ.get("EC2_PRIVATE_KEY", getattr(args, "ec2_private_key", default_ec2_private_key)),
        "keep_existing_tendermint_config": getattr(args, "keep_existing_tendermint_config", False),
        "output_path": getattr(args, "output_path", None),
        "node_or_group_ids": getattr(args, "node_or_group_ids", []),
        "fail_on_missing": not getattr(args, "no_fail_on_missing", False),
    }
    sys.exit(tmtestnet(args.config, args.command, args.subcommand, **kwargs))



# -----------------------------------------------------------------------------
#
#   Constants
#
# -----------------------------------------------------------------------------

SUPPORTED_REGIONS = {
    "us_east_1",
    "us_east_2",
    "us_west_1",
    "ap_northeast_2",
    "ap_southeast_2",
    "eu_central_1",
    "eu_west_1",
}


ALLOWED_GROUP_NAME_CHARSET = set(string.ascii_letters + string.digits + "_-")


ENV_VAR_MATCHERS = [
    re.compile(r"\$\{(?P<env_var_name>[^}^{]+)\}"),
    re.compile(r"\$(?P<env_var_name>[A-Za-z0-9_]+)"),
]


VALID_BROADCAST_TX_METHODS = {"async", "sync", "commit"}


MONITOR_INPUT_VARS_TEMPLATE = """influxdb_password = \"%(influxdb_password)s\"
keypair_name = \"%(keypair_name)s\"
instance_type = \"%(instance_type)s\"
group = \"%(resource_group_id)s\"
volume_size = %(volume_size)d
"""


MONITOR_OUTPUT_VARS_TEMPLATE = """host:
  public_dns: "{{ monitoring.outputs.host.value.public_dns }}"
  public_ip: "{{ monitoring.outputs.host.value.public_ip }}"
influxdb_url: "{{ monitoring.outputs.influxdb_url.value }}"
grafana_url: "{{ monitoring.outputs.grafana_url.value }}"
"""


TENDERMINT_INPUT_VARS_TEMPLATE = """keypair_name = \"%(keypair_name)s\"
influxdb_url = \"%(influxdb_url)s\"
influxdb_password = \"%(influxdb_password)s\"
group = \"%(resource_group_id)s__%(node_group)s\"
instance_type = \"%(instance_type)s\"
volume_size = %(volume_size)d
nodes_useast1 = %(nodes_useast1)d
startid_useast1 = %(startid_useast1)d
nodes_uswest1 = %(nodes_uswest1)d
startid_uswest1 = %(startid_uswest1)d
nodes_useast2 = %(nodes_useast2)d
startid_useast2 = %(startid_useast2)d
nodes_apnortheast2 = %(nodes_apnortheast2)d
startid_apnortheast2 = %(startid_apnortheast2)d
nodes_apsoutheast2 = %(nodes_apsoutheast2)d
startid_apsoutheast2 = %(startid_apsoutheast2)d
nodes_eucentral1 = %(nodes_eucentral1)d
startid_eucentral1 = %(startid_eucentral1)d
nodes_euwest1 = %(nodes_euwest1)d
startid_euwest1 = %(startid_euwest1)d
"""


TENDERMINT_OUTPUT_VARS_TEMPLATE = """hosts:
{% for region, hosts in tendermint.outputs.items() %}{% if hosts.value %}
  {{ region }}:{% for node_id, node in hosts.value.items() %} 
    - {{ node_id }}:
        public_dns: {{ node.public_dns }}
        public_ip: {{ node.public_ip }}
{% endfor %}{% endif %}{% endfor %}
"""


TMTESTNET_HOME = os.environ.get("TMTESTNET_HOME", "~/.tmtestnet")


# -----------------------------------------------------------------------------
#
#   Core functionality
#
# -----------------------------------------------------------------------------


def tmtestnet(cfg_file, command, subcommand, **kwargs) -> int:
    """The primary programmatic interface to the tmtestnet tool. Allows the
    tool to be imported from other Python code. Returns the intended exit code
    from execution."""

    try:
        cfg = load_testnet_config(cfg_file)
    except Exception as e:
        logger.error("Failed to load configuration from file: %s", cfg_file)
        logger.exception(e)
        return 1

    fn = None

    if command == "network":
        if subcommand == "deploy":
            fn = network_deploy
        elif subcommand == "destroy":
            fn = network_destroy
        elif subcommand == "start":
            fn = network_start
        elif subcommand == "stop":
            fn = network_stop
        elif subcommand == "fetch_logs":
            fn = network_fetch_logs

    if fn is None:    
        logger.error("Command/sub-command not yet supported: %s %s", command, subcommand)
        return 1

    try:
        fn(cfg, **kwargs)
    except Exception as e:
        logger.error("Failed to execute \"%s %s\" for configuration file: %s", command, subcommand, cfg_file)
        logger.exception(e)
        return 1

    return 0


def network_deploy(
    cfg: "TestnetConfig", 
    aws_keypair_name: str = None,
    ec2_private_key_path: str = None,
    keep_existing_tendermint_config: bool = False,
    **kwargs,
):
    """Deploys the network according to the given configuration."""
    if not aws_keypair_name:
        raise Exception("Missing AWS keypair name")
    if not os.path.exists(ec2_private_key_path):
        raise Exception("Cannot find EC2 private key: %s" % ec2_private_key_path)

    # first we get the Tendermint network config, so we can validate and
    # download any binaries we may need
    binaries_path = os.path.join(cfg.home, "bin")
    binaries = ensure_tendermint_binaries(cfg.node_groups, binaries_path)

    testnet_home = os.path.join(cfg.home, cfg.id)

    # next up, optionally deploy monitoring
    influxdb_url = cfg.monitoring.influxdb.url
    monitoring_outputs = None
    if cfg.monitoring.influxdb.enabled and cfg.monitoring.influxdb.deploy:
        monitoring_outputs = terraform_deploy_monitoring(
            os.path.join(testnet_home, "monitoring"),
            aws_keypair_name,
            cfg.id,
            cfg.monitoring.influxdb.password,
            cfg.monitoring.influxdb.instance_type,
            cfg.monitoring.influxdb.volume_size,
        )
        influxdb_url = monitoring_outputs["influxdb_url"]
    
    # deploy the Tendermint nodes
    tendermint_outputs = OrderedDict()
    for name, node_group_cfg in cfg.node_groups.items():
        tendermint_outputs[name] = terraform_deploy_tendermint_node_group(
            os.path.join(testnet_home, "tendermint", name),
            aws_keypair_name,
            cfg.id,
            name,
            influxdb_url,
            cfg.monitoring.influxdb.password,
            node_group_cfg.instance_type,
            node_group_cfg.volume_size,
            node_group_cfg.regions,
        )

    # then we ensure that all Tendermint services have been stopped if we have
    # anything at all running at the moment, otherwise this could cause problems
    network_stop(
        cfg, 
        fail_on_missing=False, 
        fail_on_error=False, 
        ec2_private_key_path=ec2_private_key_path,
    )

    # generate the Tendermint network configuration
    tendermint_config = OrderedDict()
    for node_group_name, node_group_outputs in tendermint_outputs.items():
        node_group_cfg = cfg.node_groups[node_group_name]
        node_count = len(node_group_outputs["inventory_ordered"])
        # if we're generating configuration
        if node_group_cfg.generate_tendermint_config:
            config_path = os.path.join(testnet_home, "tendermint", node_group_name, "config")
            tendermint_config[node_group_name] = tendermint_generate_config(
                config_path,
                node_group_name,
                node_group_cfg.config_template,
                node_count if node_group_cfg.validators else 0,
                0 if node_group_cfg.validators else node_count,
                node_group_outputs["inventory_ordered"],
                keep_existing_tendermint_config,
            )
        else:
            # if we're just loading/modifying existing configuration
            tendermint_config[node_group_name] = tendermint_load_nodes_config(
                node_group_cfg.custom_tendermint_config_root,
                node_count,
            )

    # reconcile the configuration across the nodes
    tendermint_finalize_config(cfg, tendermint_config)

    # keep track of which groups need to be started
    start_groups = []
    # deploy all node groups' configuration and start the relevant nodes
    for node_group_name, node_group_outputs in tendermint_outputs.items():
        node_group_cfg = cfg.node_groups[node_group_name]
        if node_group_cfg.generate_tendermint_config:
            config_path = os.path.join(testnet_home, "tendermint", node_group_name, "config")
        else:
            config_path = node_group_cfg.custom_tendermint_config_root
        ansible_deploy_tendermint_node_group(
            os.path.join(testnet_home, "tendermint", node_group_name),
            node_group_outputs["inventory_file"],
            config_path,
            binaries[node_group_cfg.binary],
            node_group_cfg.service_state,
            node_group_cfg.abci,
            ec2_private_key_path,
        )
        if node_group_cfg.service_state in ["started", "restarted"]:
            start_groups.append(node_group_name)

    # start all nodes (that we want started) simultaneously
    network_start(
        cfg,
        node_or_group_ids=start_groups,
        ec2_private_key_path=ec2_private_key_path,
    )

    logger.info("Success!")


def network_destroy(cfg: "TestnetConfig", **kwargs):
    """Destroys the network according to the given configuration."""
    testnet_home = os.path.join(cfg.home, cfg.id)
    for name, _ in reversed(cfg.node_groups.items()):
        terraform_destroy_tendermint_node_group(os.path.join(testnet_home, "tendermint", name))

    if cfg.monitoring.influxdb.enabled and cfg.monitoring.influxdb.deploy:
        terraform_destroy_monitoring(os.path.join(testnet_home, "monitoring"))


def network_state(
    cfg: "TestnetConfig", 
    state: str,
    node_or_group_ids: List[str] = None,
    ec2_private_key_path: str = None,
    fail_on_missing: bool = True,
    fail_on_error: bool = True,
    **kwargs,
):
    if not os.path.exists(ec2_private_key_path):
        raise Exception("Cannot find EC2 private key: %s" % ec2_private_key_path)

    testnet_home = os.path.join(cfg.home, cfg.id)
    target_refs = as_testnet_node_refs(
        node_or_group_ids or [],
        "from command line parameter(s)",
    )
    # if we have no targets, assume all groups are targets
    if len(target_refs) == 0:
        for node_group_name, _ in cfg.node_groups.items():
            target_refs.append(TestnetNodeRef(group=node_group_name))
    logger.info("Attempting to change state of network component(s): %s", testnet_node_refs_to_str(target_refs))
    ansible_set_tendermint_nodes_state(
        os.path.join(testnet_home, "tendermint"),
        target_refs,
        dict([(name, node_group.abci) for name, node_group in cfg.node_groups.items()]),
        cfg.abci,
        ec2_private_key_path,
        state,
        fail_on_missing=fail_on_missing,
        fail_on_error=fail_on_error,
    )
    logger.info("Successfully changed state of network component(s)")


def network_start(cfg: "TestnetConfig", **kwargs):
    network_state(cfg, "started", **kwargs)


def network_stop(cfg: "TestnetConfig", **kwargs):
    network_state(cfg, "stopped", **kwargs)


def network_fetch_logs(
    cfg: "TestnetConfig", 
    output_path=None, 
    node_or_group_ids=None,
    ec2_private_key_path=None,
    **kwargs):
    if output_path is None or len(output_path) == 0:
        raise Exception("fetch_logs command requires an output path parameter")
    if not os.path.exists(ec2_private_key_path):
        raise Exception("Cannot find EC2 private key: %s" % ec2_private_key_path)
    
    testnet_home = os.path.join(cfg.home, cfg.id)
    target_refs = as_testnet_node_refs(
        node_or_group_ids or [],
        "from command line parameter(s)",
    )
    # if we have no targets, assume all groups are targets
    if len(target_refs) == 0:
        for node_group_name, _ in cfg.node_groups.items():
            target_refs.append(TestnetNodeRef(group=node_group_name))

    logger.info("Fetching logs")
    ansible_fetch_logs(
        os.path.join(testnet_home, "tendermint"),
        target_refs,
        resolve_relative_path(output_path, os.getcwd()),
        ec2_private_key_path,
    )


# -----------------------------------------------------------------------------
#
#   Configuration
#
# -----------------------------------------------------------------------------


TestnetConfig = namedtuple("TestnetConfig",
    ["id", "monitoring", "abci", "node_groups", "load_tests", "home", "tendermint_binaries"],
    defaults=[None, None, dict(), OrderedDict(), OrderedDict(), TMTESTNET_HOME, dict()],
)
TestnetMonitoringConfig = namedtuple("TestnetMonitoringConfig",
    ["signalfx", "influxdb"],
    defaults=[None, None],
)
TestnetSignalFXConfig = namedtuple("TestnetSignalFXConfig",
    ["enabled", "api_token", "realm"],
    defaults=[False, None, None],
)
TestnetInfluxDBConfig = namedtuple("TestnetInfluxDBConfig",
    ["enabled", "deploy", "region", "url", "password", "instance_type", "volume_size"],
    defaults=[False, False, "us-east-1", None, None, "t3.small", 10],
)
TestnetNodeGroupConfig = namedtuple("TestnetNodeGroupConfig",
    [
        "binary", "abci", "validators", "in_genesis", "power", "service_state",
        "config_template", "use_seeds", "persistent_peers", "regions", 
        "instance_type", "volume_size", "generate_tendermint_config",
        "custom_tendermint_config_root",
    ],
    defaults=[
        None, None, True, True, 1000, "started",
        None, [], [], OrderedDict(), 
        "t3.small", 8, True,
        None,
    ],
)
TestnetABCIConfig = namedtuple("TestnetABCIConfig",
    ["deploy", "start", "stop"],
)
TestnetABCIPlaybookConfig = namedtuple("TestnetABCIPlaybookConfig",
    ["playbook", "extra_vars"],
    defaults=[None, dict()],
)
TestnetTMBenchConfig = namedtuple("TestnetTMBenchConfig",
    ["client_nodes", "targets", "time", "broadcast_tx_method", "connections", "rate", "size"],
    defaults=[1, [], 60, "async", 1, 1000, 250],
)
TestnetRegionConfig = namedtuple("TestnetRegionConfig",
    ["node_count", "start_id"],
    defaults=[0, 0],
)
TestnetNodeRef = namedtuple("TestnetNodeRef",
    ["group", "id"],
    defaults=[None, None],
)
TestnetHostRef = namedtuple("TestnetHostRef",
    ["group", "id", "hostname"],
    defaults=[None, None, None],
)


TendermintNodeConfig = namedtuple("TendermintNodeConfig",
    ["config_path", "config", "priv_validator_key", "node_key", "peer_id"],
)
TendermintNodePrivValidatorKey = namedtuple("TendermintNodePrivValidatorKey",
    ["address", "pub_key", "priv_key"],
)
TendermintNodeKey = namedtuple("TendermintNodeKey", 
    ["type", "value"],
)


LOAD_TEST_METHODS = {
    "tm-bench": TestnetTMBenchConfig,
}


def load_testnet_config(filename: str) -> TestnetConfig:
    """Loads the configuration from the given file. Throws an exception if any
    validation fails. On success, returns the configuration."""

    # resolve the tmtestnet home folder path
    tmtestnet_home = os.path.expanduser(TMTESTNET_HOME)
    ensure_path_exists(tmtestnet_home)

    with open(filename, "rt") as f:
        cfg_dict = yaml.safe_load(f)

    if "id" not in cfg_dict:
        raise Exception("Missing required \"id\" parameter in configuration file")

    config_base_path = os.path.dirname(os.path.abspath(filename))
    abci_config = load_abci_configs(cfg_dict.get("abci", dict()), config_base_path)
    return TestnetConfig(
        id=cfg_dict["id"],
        monitoring=load_monitoring_config(cfg_dict.get("monitoring", dict())),
        abci=abci_config,
        node_groups=load_node_groups_config(cfg_dict.get("node_groups", []), config_base_path, abci_config),
        load_tests=load_load_tests_config(cfg_dict.get("load_tests", [])),
        home=tmtestnet_home,
    )


def load_monitoring_config(cfg_dict: Dict) -> TestnetMonitoringConfig:
    return TestnetMonitoringConfig(
        signalfx=TestnetSignalFXConfig(**cfg_dict.get("signalfx", dict())),
        influxdb=TestnetInfluxDBConfig(**cfg_dict.get("influxdb", dict())),
    )


def load_abci_configs(cfg_dict: Dict, config_base_path: str) -> Dict:
    # it's okay for this to be None, which disables any ABCI deployment
    if cfg_dict is None or len(cfg_dict) == 0:
        return dict()
    
    result = dict()
    for abci_config_name, abci_config in cfg_dict.items():
        result[abci_config_name] = load_abci_config(
            abci_config,
            config_base_path,
            "in \"abci\" configuration for \"%s\"" % abci_config_name,
        )
    return result


def load_abci_config(cfg_dict: Dict, config_base_path: str, ctx: str) -> TestnetABCIConfig:
    if not isinstance(cfg_dict, dict) or len(cfg_dict) == 0:
        raise Exception("Invalid ABCI configuration (%s)" % ctx)

    required_fields = ["deploy", "start", "stop"]
    _cfg_dict = dict()
    for f in required_fields:
        if f not in cfg_dict:
            raise Exception("Missing required field \"%s\" in ABCI app configuration (%s)" % (f, ctx))
        _cfg_dict[f] = load_abci_playbook_config(cfg_dict[f], config_base_path, "for %s stage, %s" % (f, ctx))
    return TestnetABCIConfig(**_cfg_dict)


def load_abci_playbook_config(cfg_dict: Dict, config_base_path: str, ctx: str) -> TestnetABCIPlaybookConfig:
    if not isinstance(cfg_dict, dict):
        raise Exception("Invalid ABCI playbook configuration (%s)" % ctx)
    if "playbook" not in cfg_dict:
        raise Exception("Missing required field \"playbook\" in ABCI app configuration (%s)" % ctx)
    _cfg_dict = deepcopy(cfg_dict)
    _cfg_dict["playbook"] = resolve_relative_path(cfg_dict["playbook"], config_base_path)
    if not os.path.isfile(_cfg_dict["playbook"]):
        raise Exception("Cannot find Ansible playbook: %s (%s)" % (_cfg_dict["playbook"], ctx))
    return TestnetABCIPlaybookConfig(**cfg_dict)


def load_node_groups_config(
    cfg_list: List, 
    config_base_path: str,
    abci_config: TestnetABCIConfig,
) -> OrderedDictType[str, TestnetNodeGroupConfig]:
    return as_ordered_dict(
        cfg_list,
        "in \"node_groups\" configuration",
        value_transform=load_node_group_config,
        additional_params={"config_base_path": config_base_path, "abci_config": abci_config},
    )


def load_load_tests_config(cfg_list: list) -> OrderedDictType:
    return as_ordered_dict(
        cfg_list,
        "in \"load_tests\" configuration",
        value_transform=load_load_test_config,
    )


def load_node_group_config(
    cfg_dict: dict, 
    ctx: str, 
    config_base_path: str = None,
    abci_config: TestnetABCIConfig = None,
) -> TestnetNodeGroupConfig:
    # don't modify the original config
    _cfg_dict = deepcopy(cfg_dict)
    _cfg_dict["regions"] = parse_regions_list(
        cfg_dict.get("regions", None),
        ctx,
    )
    _cfg_dict["use_seeds"] = as_testnet_node_refs(cfg_dict.get("use_seeds", dict()), "in \"use_seeds\", %s" % ctx)
    _cfg_dict["persistent_peers"] = as_testnet_node_refs(cfg_dict.get("persistent_peers", dict()), "in \"persistent_peers\", %s" % ctx)
    # if a configuration template's been specified
    if "config_template" in cfg_dict and len(cfg_dict["config_template"]) > 0:
        _cfg_dict["config_template"] = resolve_relative_path(cfg_dict["config_template"], config_base_path)
        if not os.path.isfile(_cfg_dict["config_template"]):
            raise Exception("Cannot find configuration template: %s (%s)" % (_cfg_dict["config_template"], ctx))
    if "abci" in _cfg_dict and _cfg_dict["abci"] not in abci_config:
        raise Exception("Unrecognized ABCI configuration: %s (%s)" % (_cfg_dict["abci"], ctx))
    return TestnetNodeGroupConfig(**_cfg_dict)


def load_load_test_config(cfg_dict: dict, ctx: str):
    method = cfg_dict.get("method", None)
    if method not in LOAD_TEST_METHODS:
        raise Exception("Invalid method (%s)" % ctx)
    _cfg_dict = deepcopy(cfg_dict)
    if "method" in _cfg_dict:
        del _cfg_dict["method"]
    return LOAD_TEST_METHODS[method](**_cfg_dict)


def load_tendermint_priv_validator_key(path: str) -> TendermintNodePrivValidatorKey:
    with open(path, "rt") as f:
        priv_val_key = json.load(f)
    for field in ["address", "pub_key", "priv_key"]:
        if field not in priv_val_key:
            raise Exception("Missing field \"%s\" in %s" % (field, path))
    cfg = {
        "address": priv_val_key["address"],
        "pub_key": load_key(priv_val_key["pub_key"], "pub_key in %s" % path),
        "priv_key": load_key(priv_val_key["priv_key"], "priv_key in %s" % path),
    }
    return TendermintNodePrivValidatorKey(**cfg)


def load_key(d, ctx) -> TendermintNodeKey:
    if not isinstance(d, dict):
        raise Exception("Expected key to consist of key/value pairs (%s)" % ctx)
    return TendermintNodeKey(**d)


# -----------------------------------------------------------------------------
#
#   Network Management
#
# -----------------------------------------------------------------------------


def terraform_deploy_monitoring(
    workdir,
    keypair_name,
    resource_group_id, 
    influxdb_password, 
    instance_type, 
    volume_size,
):
    """Deploys the Grafana/InfluxDB monitoring service on AWS with the given
    parameters."""
    ensure_path_exists(workdir)
    output_vars_template = os.path.join(workdir, "terraform-output-vars.yaml.jinja2")
    with open(output_vars_template, "wt") as f:
        f.write(MONITOR_OUTPUT_VARS_TEMPLATE)
    output_vars_file = os.path.join(workdir, "terraform-output-vars.yaml")
    input_vars_file = os.path.join(workdir, "terraform-input-vars.tfvars")
    extra_vars_file = os.path.join(workdir, "terraform-extra-vars.yaml")
    with open(input_vars_file, "wt") as f:
        f.write(MONITOR_INPUT_VARS_TEMPLATE % {
            "keypair_name": keypair_name,
            "resource_group_id": resource_group_id,
            "influxdb_password": influxdb_password,
            "instance_type": instance_type,
            "volume_size": volume_size,
        })
    extra_vars = {
        "state": "present",
        "resource_group_id": resource_group_id,
        "input_vars_file": input_vars_file,
        "output_vars_template": output_vars_template,
        "output_vars_file": output_vars_file,
    }
    save_yaml_config(extra_vars_file, extra_vars)

    logger.info("Deploying Grafana/InfluxDB monitoring")
    sh([
        "ansible-playbook", 
        "-e", "@%s" % extra_vars_file,
        "monitor.yaml",
    ])
    logger.info("Monitoring successfully deployed")

    # read the output variables that the Ansible script should have generated
    output_vars = load_yaml_config(output_vars_file)
    # add this host's SSH key to our known_hosts
    ensure_in_known_hosts(output_vars["host"]["public_dns"])
    return output_vars


def terraform_destroy_monitoring(workdir):
    """Deploys the Grafana/InfluxDB monitoring service on AWS with the given
    parameters."""
    extra_vars_file = os.path.join(workdir, "terraform-extra-vars.yaml")
    if not os.path.isfile(extra_vars_file):
        raise Exception("Cannot find %s when attempting to destroy monitoring deployment" % extra_vars_file)
    
    # Reopen the extra vars file, but just change the desired state
    extra_vars = load_yaml_config(extra_vars_file)
    extra_vars["state"] = "absent"
    save_yaml_config(extra_vars_file, extra_vars)

    logger.info("Destroying Grafana/InfluxDB monitoring")
    sh([
        "ansible-playbook", 
        "-e", "@%s" % extra_vars_file,
        "monitor.yaml",
    ])
    logger.info("Monitoring successfully destroyed")


def terraform_deploy_tendermint_node_group(
    workdir,
    keypair_name,
    resource_group_id,
    node_group_name,
    influxdb_url,
    influxdb_password,
    instance_type,
    volume_size,
    regions: OrderedDictType[str, "TestnetRegionConfig"],
):
    ensure_path_exists(workdir)
    output_vars_template = os.path.join(workdir, "output-vars.yaml.jinja2")
    with open(output_vars_template, "wt") as f:
        f.write(TENDERMINT_OUTPUT_VARS_TEMPLATE)
    output_vars_file = os.path.join(workdir, "output-vars.yaml")
    input_vars_file = os.path.join(workdir, "terraform-input-vars.tfvars")
    extra_vars_file = os.path.join(workdir, "terraform-extra-vars.yaml")
    with open(input_vars_file, "wt") as f:
        input_vars = {
            "keypair_name": keypair_name,
            "resource_group_id": resource_group_id,
            "node_group": node_group_name,
            "influxdb_url": influxdb_url,
            "influxdb_password": influxdb_password,
            "instance_type": instance_type,
            "volume_size": volume_size,
        }
        for region_id, region in regions.items():
            shortened_region_id = region_id.replace("_", "")
            input_vars["nodes_%s" % shortened_region_id] = region.node_count
            input_vars["startid_%s" % shortened_region_id] = region.start_id
        f.write(TENDERMINT_INPUT_VARS_TEMPLATE % input_vars)
    extra_vars = {
        "state": "present",
        "resource_group_id": resource_group_id,
        "node_group": node_group_name,
        "input_vars_file": input_vars_file,
        "output_vars_template": output_vars_template,
        "output_vars_file": output_vars_file,
    }
    save_yaml_config(extra_vars_file, extra_vars)

    logger.info("Deploying Tendermint node group: %s", node_group_name)
    sh([
        "ansible-playbook", 
        "-e", "@%s" % extra_vars_file,
        "tendermint.yaml",
    ])
    logger.info("Tendermint node group successfully deployed")

    # read the output variables that the Ansible script should have generated
    output_vars = load_yaml_config(output_vars_file)
    inventory = dict()
    for _, node_list in output_vars["hosts"].items():
        for node in node_list:
            node_id, = node.keys()
            node_details, = node.values()
            inventory[node_id] = node_details["public_dns"]
    inventory_ordered = OrderedDict()
    for i in range(len(inventory)):
        node_id = "node%d" % i
        inventory_ordered[node_id] = inventory[node_id]

    # write an Ansible inventory file for the deployed hosts
    inventory_file = os.path.join(workdir, "hosts")
    with open(inventory_file, "wt") as f:
        f.write("[tendermint]\n")
        for node_id, node_dns in inventory_ordered.items():
            f.write("%s ansible_ssh_host=%s\n" % (node_id, node_dns))
    output_vars["inventory_file"] = inventory_file
    output_vars["inventory_ordered"] = [node_dns for _, node_dns in inventory_ordered.items()]
    logger.debug("Wrote Ansible inventory for group %s to file: %s", node_group_name, inventory_file)
    # overwrite the output variables file with the new inventory_file parameter
    save_yaml_config(output_vars_file, output_vars)
    # add all of the hosts' SSH keys to the known_hosts file on the local machine
    ensure_all_in_known_hosts(output_vars["inventory_ordered"])
    return output_vars


def terraform_destroy_tendermint_node_group(workdir):
    extra_vars_file = os.path.join(workdir, "terraform-extra-vars.yaml")
    if not os.path.isfile(extra_vars_file):
        raise Exception("Cannot find %s when attempting to destroy Tendermint deployment" % extra_vars_file)
    
    # Reopen the extra vars file, but just change the desired state
    with open(extra_vars_file, "rt") as f:
        extra_vars = yaml.safe_load(f)
    extra_vars["state"] = "absent"
    with open(extra_vars_file, "wt") as f:
        yaml.safe_dump(extra_vars, f)

    logger.info("Destroying Tendermint node group: %s", extra_vars["node_group"])
    sh([
        "ansible-playbook", 
        "-e", "@%s" % extra_vars_file,
        "tendermint.yaml",
    ])
    logger.info("Tendermint node group successfully destroyed: %s", extra_vars["node_group"])


def tendermint_generate_config(
    workdir: str,
    node_group_name: str,
    config_file_template: str,
    validators: int,
    non_validators: int,
    hostnames: List[str],
    keep_existing: bool,
) -> List[TendermintNodeConfig]:
    """Generates the Tendermint network configuration for a node group."""
    logger.info("Generating Tendermint configuration for node group: %s", node_group_name)
    if os.path.isdir(workdir):
        if keep_existing:
            logger.info("Configuration already exists, keeping existing configuration")
            return tendermint_load_nodes_config(workdir, len(hostnames))

        logger.info("Removing existing configuration directory: %s", workdir)
        shutil.rmtree(workdir)
    ensure_path_exists(workdir)
    cmd = [
        "tendermint", "testnet",
        "--v", "%d" % validators,
        "--n", "%d" % non_validators,
        "--populate-persistent-peers=false", # we'll handle this ourselves later
        "--o", workdir,
    ]
    if config_file_template is not None:
        cmd.extend(["--config", config_file_template])
    for hostname in hostnames:
        cmd.extend(["--hostname", hostname])
    sh(cmd)
    return tendermint_load_nodes_config(workdir, len(hostnames))


def tendermint_load_nodes_config(base_path: str, node_count: int) -> List[TendermintNodeConfig]:
    """Loads the relevant Tendermint node configuration for all nodes in the
    given base path."""
    logger.debug("Loading Tendermint node group configuration for %d nodes from %s", node_count, base_path)
    result = []
    for i in range(node_count):
        node_id = "node%d" % i
        host_cfg_path = os.path.join(base_path, node_id, "config")
        config_file = os.path.join(host_cfg_path, "config.toml")
        config = load_toml_config(config_file)
        priv_val_key = load_tendermint_priv_validator_key(os.path.join(host_cfg_path, "priv_validator_key.json"))
        node_key = load_tendermint_node_key(os.path.join(host_cfg_path, "node_key.json"))
        result.append(
            TendermintNodeConfig(
                config_path=host_cfg_path,
                config=config,
                priv_validator_key=priv_val_key,
                node_key=node_key,
                peer_id=tendermint_peer_id(
                    config["moniker"],
                    ed25519_pub_key_to_id(
                        get_ed25519_pub_key(
                            node_key.value,
                            "node with configuration at %s" % config_file,
                        ),
                    ),
                ),
            ),
        )
    return result


def tendermint_finalize_config(cfg: "TestnetConfig", tendermint_config: Dict[str, List[TendermintNodeConfig]]):
    genesis_doc = {
        # amino is very particular about this format, and must be in UTC
        "genesis_time": pytz.utc.localize(datetime.datetime.utcnow()).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "chain_id": cfg.id,
        "validators": [],
        "app_hash": "",
    }
    for node_group_name, node_group_cfg in cfg.node_groups.items():
        # first handle persistent peers for this group
        persistent_peers = unique_peer_ids(
            node_group_cfg.persistent_peers, 
            tendermint_config,
        )
        # then handle seeds for this group
        seeds = unique_peer_ids(
            node_group_cfg.use_seeds, 
            tendermint_config,
        )

        # update this node group's configuration
        for node_cfg in tendermint_config[node_group_name]:
            _cfg = deepcopy(node_cfg.config)
            _cfg["p2p"]["persistent_peers"] = ",".join(persistent_peers - {node_cfg.peer_id})
            _cfg["p2p"]["seeds"] = ",".join(seeds - {node_cfg.peer_id})
            # write out the updated configuration TOML file
            save_toml_config(os.path.join(node_cfg.config_path, "config.toml"), _cfg)

            # if this group needs to be in the genesis file
            if node_group_cfg.validators and node_group_cfg.in_genesis:
                genesis_doc["validators"].append({
                    "address": node_cfg.priv_validator_key.address,
                    "pub_key": {
                        "type": node_cfg.priv_validator_key.pub_key.type,
                        "value": node_cfg.priv_validator_key.pub_key.value,
                    },
                    "power": "%d" % node_group_cfg.power,
                    "name": node_cfg.config["moniker"],
                })
        
    # write all nodes' genesis files
    for node_group_name, node_group_cfg in cfg.node_groups.items():
        for node_cfg in tendermint_config[node_group_name]:
            node_genesis_file = os.path.join(node_cfg.config_path, "genesis.json")
            with open(node_genesis_file, "wt") as f:
                json.dump(genesis_doc, f, indent=2)
            logger.debug("Wrote genesis file: %s", node_genesis_file)


def ansible_deploy_tendermint_node_group(
    workdir: str,
    inventory_file: str,
    config_path: str,
    binary: str,
    service_state: str,
    abci_cfg,
    ec2_private_key_path: str,
):
    logger.info("Deploying node group configuration: %s", config_path)

    logger.info("Using binary: %s", binary)
    extra_vars_file = os.path.join(workdir, "ansible-extra-vars.yaml")
    extra_vars = {
        "service_state": "stopped",
        "src_binary": binary,
        "src_config_path": config_path,
        "copy_node_config": True,
    }
    save_yaml_config(extra_vars_file, extra_vars)

    sh([
        "ansible-playbook",
        "-i", inventory_file,
        "-u", "ec2-user",
        "-e", "@%s" % extra_vars_file,
        "--private-key", ec2_private_key_path,
        os.path.join("tendermint", "ansible", "deploy.yaml"),
    ])


def ansible_set_tendermint_nodes_state(
    workdir: str,
    refs: List[TestnetNodeRef],
    node_group_abcis: Dict[str, str], # mapping of node group names to ABCI names
    abci_configs: Dict[str, TestnetABCIConfig], # mapping of ABCI config names to ABCI configs
    ec2_private_key_path: str,
    state: str,
    fail_on_missing: bool = True,
    fail_on_error: bool = True,
):
    """Attempts to collect all nodes' details from the given references list
    and ensure that they are all set to the desired state (Ansible state)."""
    valid_states = {"started", "stopped", "restarted"}
    if state not in valid_states:
        raise Exception("Desired service state must be one of: %s", ", ".join(valid_states))
    state_verb = "starting" if state in {"started", "restarted"} else "stopping"

    # get all of the host references
    host_refs = node_to_host_refs(workdir, refs, fail_on_missing=fail_on_missing)
    hostnames_by_abci = dict()
    for host_ref in host_refs:
        node_group_abci = node_group_abcis.get(host_ref.group, None)
        if node_group_abci is not None:
            if host_ref.group not in hostnames_by_abci:
                hostnames_by_abci[host_ref.group] = []
            hostnames_by_abci[host_ref.group].append(host_ref.hostname)

    if len(host_refs) == 0:
        logger.info("No deployed hosts' states to change")
        return

    logger.info("%s hosts", state_verb.capitalize())

    ok = True
    with tempfile.TemporaryDirectory() as tmpdir:
        abci_playbook_cmds = []

        inventory_file = os.path.join(tmpdir, "inventory")
        inventory = OrderedDict()
        inventory["tendermint"] = [host_ref.hostname for host_ref in host_refs]
        for abci_config_name, abci_hostnames in hostnames_by_abci.items():
            abci_cfg = abci_configs[abci_config_name].start if state in ["started", "restarted"] else abci_configs[abci_config_name].stop
            inventory[abci_config_name] = abci_hostnames
            abci_extra_vars_file = os.path.join(tmpdir, "extravars_%s.yaml" % abci_config_name)
            extra_vars = {
                "state": state,
                "hosts": abci_config_name,
            }
            if isinstance(abci_cfg.extra_vars, dict):
                extra_vars.update(abci_cfg.extra_vars)
            save_yaml_config(abci_extra_vars_file, extra_vars)
            abci_playbook_cmds.append([("%s hosts for ABCI configuration: %s" % (state_verb.capitalize(), abci_config_name),
                "ansible-playbook",
                "-i", inventory_file,
                "-u", "ec2-user",
                "-e", "@%s" % abci_extra_vars_file,
                "--private-key", ec2_private_key_path,
                abci_cfg.playbook,
            )])
        save_ansible_inventory(inventory_file, inventory)
        
        tendermint_playbook_cmd = [
            "ansible-playbook",
            "-i", inventory_file,
            "-u", "ec2-user",
            "-e", "state=%s" % state,
            "--private-key", ec2_private_key_path,
            os.path.join("tendermint", "ansible", "tendermint-state.yaml"),
        ]
        cmds = [("Changing Tendermint nodes' state", tendermint_playbook_cmd)]
        # if we're starting, we need to start the ABCI apps first
        if state in {"started", "restarted"}:
            cmds = abci_playbook_cmds + cmds
        else:
            # otherwise, if we're stopping, we need to stop the ABCI apps last
            cmds = cmds + abci_playbook_cmds

        try:
            for desc_cmd in cmds:
                desc, cmd = desc_cmd
                logger.info(desc)
                sh(cmd)
        except Exception as e:
            ok = False
            if fail_on_error:
                raise e
            logger.info("Failed %s hosts - skipping", state_verb)

    if ok:
        logger.info("Hosts' state successfully set to \"%s\"", state)


def ansible_fetch_logs(
    workdir: str,
    refs: List[TestnetNodeRef],
    output_path: str,
    ec2_private_key_path: str,
    fail_on_missing: bool = True,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        inventory_file = os.path.join(tmpdir, "inventory")
        host_refs = node_to_host_refs(workdir, refs, fail_on_missing=fail_on_missing)
        save_ansible_inventory(inventory_file, OrderedDict({
            "tendermint": [host_ref.hostname for host_ref in host_refs],
        }))
        sh([
            "ansible-playbook",
            "-i", inventory_file,
            "-u", "ec2-user",
            "-e", "local_log_path=%s" % output_path,
            "--private-key", ec2_private_key_path,
            os.path.join("tendermint", "ansible", "fetch-logs.yaml"),
        ])


# -----------------------------------------------------------------------------
#
#   Utilities
#
# -----------------------------------------------------------------------------


def sh(cmd):
    logger.info("Executing command: %s" % " ".join(cmd))
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as p:
        print("")
        for line in p.stdout:
            print(line.decode("utf-8").rstrip())
        while p.poll() is None:
            time.sleep(1)
        print("")
    
        if p.returncode != 0:
            raise Exception("Process failed with return code %d" % p.returncode)


def configure_logging(verbose=False):
    """Supercharge our logger."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s\t%(levelname)s\t%(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "bold_yellow",
                "ERROR": "bold_red",
                "CRITICAL": "bold_red",
            }
        ),
    )
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


def configure_env_var_yaml_loading(fail_on_missing=False):
    for matcher in ENV_VAR_MATCHERS:
        yaml.add_implicit_resolver("!envvar", matcher, None, yaml.SafeLoader)
    yaml.add_constructor("!envvar", make_envvar_constructor(fail_on_missing=fail_on_missing), yaml.SafeLoader)


def make_envvar_constructor(fail_on_missing=False):
    def envvar_constructor(loader, node):
        """From https://stackoverflow.com/a/52412796/1156132"""
        value = node.value
        for matcher in ENV_VAR_MATCHERS:
            match = matcher.match(value)
            if match is not None:
                env_var_name = match.group("env_var_name")
                logger.debug("Parsed environment variable: %s", env_var_name)
                if fail_on_missing and env_var_name not in os.environ:
                    raise Exception("Missing environment variable during configuration file parsing: %s" % env_var_name)
                return os.environ.get(env_var_name, "") + value[match.end():]
        raise Exception("Internal error: environment variable matching algorithm failed")
    return envvar_constructor


def as_string_list(v, ctx):
    if isinstance(v, list):
        return v
    elif isinstance(v, str):
        return [v]
    raise Exception("Expected list of strings or string (%s)" % ctx)


def as_ordered_dict(v, ctx, value_transform=None, additional_params=None):
    """Expects v to be a list containing single key/value pair entries, and
    transforms it into an ordered dictionary."""
    if not isinstance(v, list):
        raise Exception("Expected list of key/value pairs, but got: %s (%s)" % (type(v), ctx))
    i = 0
    result = OrderedDict()
    if additional_params is None:
        additional_params = dict()
    for item in v:
        if not isinstance(item, dict) or len(item) == 0:
            raise Exception("Expected item %d to be a single key/value pair (%s)" % (i, ctx))
        k, = item.keys()
        v, = item.values()
        result[k] = value_transform(v, "item %d, %s" % (i, ctx), **additional_params) if callable(value_transform) else v
        i += 1
    return result


def validate_group_name(n: str, ctx: str) -> str:
    for c in n:
        if c not in ALLOWED_GROUP_NAME_CHARSET:
            raise Exception("Invalid character in group name \"%s\": %s (%s)" % (n, c, ctx))
    return n


def as_testnet_node_ref(s: str, ctx: str) -> TestnetNodeRef:
    if "[" not in s:
        return TestnetNodeRef(group=validate_group_name(s, ctx))

    parts = s.split("[")
    if len(parts) > 2:
        raise Exception("Invalid group/node ID format: %s (%s)" % (s, ctx))
    group_name = validate_group_name(parts[0], ctx)
    try:
        node_id = int(parts[1].replace("]", ""))
    except ValueError:
        raise Exception("Expected node index to be an integer: %s (%s)" % (s, ctx))
    
    return TestnetNodeRef(group=group_name, id=node_id)


def as_testnet_node_refs(l: List[str], ctx: str) -> List[TestnetNodeRef]:
    _l = []
    i = 0
    for s in l:
        _l.append(as_testnet_node_ref(s, "entry %d, %s" % (i, ctx)))
        i += 1
    return _l


def testnet_node_ref_to_str(ref: TestnetNodeRef) -> str:
    return ("%s" % ref.group) if ref.id is None else ("%s[%d]" % (ref.group, ref.id))


def testnet_node_refs_to_str(refs: List[TestnetNodeRef]) -> str:
    return ", ".join([testnet_node_ref_to_str(ref) for ref in refs])


def github_release_url(filename, version):
    return "https://github.com/tendermint/tendermint/releases/download/%s/%s" % (version, filename)


def download(url, filename):
    logger.info("Downloading: %s", url)
    with open(filename, "wb") as f:
        response = requests.get(url)
        if response.status_code >= 400:
            logger.error("Got HTTP response code %d: %s", response.status_code, response.content)
            raise Exception("Failed to download file from URL: %s" % url)
        f.write(response.content)


def load_sha256sums(filename):
    sha256sums = {}
    with open(filename, "rt") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 2:
                raise Exception("Failed to process SHA256 sums for file: %s (incorrect format)" % filename)
            sha256sums[parts[1]] = parts[0]
    return sha256sums


def validate_sha256sum(filename, expected_hash):
    logger.debug("Validating SHA256 hash of file: %s", filename)
    with open(filename, "rb") as f:
        sha256 = hashlib.sha256()
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha256.update(chunk)
    eh = expected_hash.lower()
    ah = sha256.hexdigest().lower()
    if ah != eh:
        raise Exception("Expected SHA256 hash of %s to be %s, but was %s" % (filename, eh, ah))


def resolve_relative_path(path: str, base_path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_path, path))


def load_toml_config(filename):
    logger.debug("Loading TOML configuration file: %s", filename)
    with open(filename, "rt") as f:
        return toml.load(f)

    
def save_toml_config(filename, cfg):
    with open(filename, "wt") as f:
        toml.dump(cfg, f)
    logger.debug("Wrote configuration to %s", filename)


def load_yaml_config(filename):
    with open(filename, "rt") as f:
        return yaml.safe_load(f)


def save_yaml_config(filename, cfg):
    with open(filename, "wt") as f:
        yaml.safe_dump(cfg, f)
    logger.debug("Wrote configuration to %s", filename)


def ensure_tendermint_binary(path: str, download_path: str) -> str:
    if not path.startswith("v"):
        if not os.path.isfile(path):
            raise Exception("Cannot find binary at path: %s" % path)
        return path

    version = path
    logger.info("Checking for locally downloaded Tendermint binary: %s", version)
    release_zip = "tendermint_%s_linux_amd64.zip" % version
    base_path = os.path.join(download_path, version)
    ensure_path_exists(base_path)
    zip_path = os.path.join(base_path, release_zip)
    shasums_path = os.path.join(base_path, "SHA256SUMS")
    bin_path = os.path.join(base_path, "tendermint")
    if not os.path.isfile(shasums_path):
        download(github_release_url("SHA256SUMS", version), shasums_path)
    sha256sums = load_sha256sums(shasums_path)
    if release_zip not in sha256sums:
        raise Exception("Missing Tendermint release zipfile SHA256 sum in SHA256SUMS file: %s" % release_zip)
    if not os.path.isfile(zip_path):
        download(github_release_url(release_zip, version), zip_path)
    validate_sha256sum(zip_path, sha256sums[release_zip])
    # extract the contents of the zip file
    logger.info("Extracting %s", zip_path)
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extract("tendermint", path=base_path)
    logger.debug("Using locally downloaded Tendermint binary: %s", bin_path)
    return bin_path


def ensure_tendermint_binaries(cfg: OrderedDictType[str, TestnetNodeGroupConfig], download_path: str):
    ensure_path_exists(download_path)
    seen_bins = set()
    result = dict()
    for _, node_group_cfg in cfg.items():
        binary = node_group_cfg.binary
        if binary in seen_bins:
            continue
        seen_bins.add(binary)
        result[binary] = ensure_tendermint_binary(binary, download_path)
    return result


def ensure_path_exists(path):
    if not os.path.isdir(path):
        os.makedirs(path, mode=0o755, exist_ok=True)
        logger.debug("Created folder: %s", path)


def parse_regions_list(regions_list: list, ctx: str) -> OrderedDictType[str, TestnetRegionConfig]:
    if not isinstance(regions_list, list):
        raise Exception("Expected \"regions\" parameter to be a list of key/value pairs, but was %s (%s)" % (type(regions_list), ctx))
    result = OrderedDict()
    start_id = 0
    i = 0
    seen_regions = set()
    for region in regions_list:
        if not isinstance(region, dict) or len(region) != 1:
            raise Exception("Expected \"regions\" item %d to be a single key/value pair (%s)" % (i, ctx))
        region_id, = region.keys()
        if region_id not in SUPPORTED_REGIONS:
            raise Exception("Unsupported region \"%s\" in item %d (%s)" % (region_id, i, ctx))
        if region_id in seen_regions:
            raise Exception("Duplicate region \"%s\" in item %d (%s)" % (region_id, i, ctx))
        seen_regions.add(region_id)
        node_count, = region.values()
        result[region_id] = TestnetRegionConfig(
            node_count=node_count, 
            start_id=start_id,
        )
        start_id += node_count
        i += 1
    for unseen_region in (SUPPORTED_REGIONS - seen_regions):
        result[unseen_region] = TestnetRegionConfig(
            node_count=0,
            start_id=0,
        )
    return result


def get_host_keys(hostname, retries=10, retry_wait=5):
    """Calls ssh-keyscan for the given hostname to get its keys."""
    for i in range(retries):
        logger.debug("Scanning keys for host: %s", hostname)
        keys = []
        with subprocess.Popen(["ssh-keyscan", hostname], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
            for line in p.stdout:
                key = line.decode("utf-8").rstrip()
                if len(key) > 0:
                    keys.append(key)
            while p.poll() is None:
                time.sleep(1)

            if p.returncode == 0 and len(keys) > 0:
                return keys
            elif i < (retries-1):
                logger.warning("ssh-keyscan failed with return code %d and %d keys - trying again in %d seconds" % (p.returncode, len(keys), retry_wait))
                time.sleep(retry_wait)
    raise Exception("Call to ssh-keyscan failed with return code %d" % p.returncode)


def clear_host_keys(hostname):
    logger.debug("Removing any existing keys for host: %s", hostname)
    with subprocess.Popen(["ssh-keygen", "-R", hostname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as p:
        while p.poll() is None:
            time.sleep(1)
        if p.returncode != 0:
            raise Exception("Call to ssh-keygen failed with return code %d" % p.returncode)


def ensure_in_known_hosts(hostname):
    """Calls ssh-keyscan for the given host and ensures that all relevant keys
    for the host are in the user's known_hosts file."""
    known_hosts = os.path.expanduser("~/.ssh/known_hosts")
    # clear any existing keys for the host
    clear_host_keys(hostname)
    host_keys = get_host_keys(hostname)
    # add these keys to the known_hosts file
    with open(known_hosts, "at") as f:
        for key in host_keys:
            f.write("%s\n" % key)


def ensure_all_in_known_hosts(hostnames):
    """Runs ensure_in_known_hosts() for each of the given hostnames."""
    logger.info("Adding all target nodes' SSH keys to local known_hosts")
    for hostname in hostnames:
        ensure_in_known_hosts(hostname)


def tendermint_peer_id(host: str, address: str = None) -> str:
    return ("%s@%s:26656" % (address, host)) if address is not None else ("%s:26656" % host)


def get_current_user() -> str:
    return pwd.getpwuid(os.getuid())[0]


def load_tendermint_node_key(filename: str) -> TendermintNodeKey:
    """Loads the node's private key from the given file."""
    with open(filename, "rt") as f:
        node_key = json.load(f)
    if "priv_key" not in node_key:
        raise Exception("Invalid node key format in file: %s" % filename)
    if node_key["priv_key"].get("type", "") != "tendermint/PrivKeyEd25519":
        raise Exception("The only node key type currently supported is tendermint/PrivKeyEd25519: %s" % filename)
    return TendermintNodeKey(**node_key["priv_key"])


def get_ed25519_pub_key(priv_key: str, ctx: str) -> bytes:
    """Returns the public key associated with the given private key. Assumes
    that the priv_key is provided in base64, and the latter half of the private
    key is the public key."""
    priv_key_bytes = base64.b64decode(priv_key)
    if len(priv_key_bytes) != 64:
        raise Exception("Invalid ed25519 private key: %s (%s)" % (priv_key, ctx))
    pub_key_bytes = priv_key_bytes[32:]
    if sum(pub_key_bytes) == 0:
        raise Exception("Public key bytes in ed25519 private key not initialized: %s (%s)" % (priv_key, ctx))
    return pub_key_bytes


def ed25519_pub_key_to_id(pub_key: bytes) -> str:
    """Converts the given ed25519 public key into a Tendermint-compatible ID."""
    sum_truncated = hashlib.sha256(pub_key).digest()[:20]
    return "".join(["%.2x" % b for b in sum_truncated])


def unique_peer_ids(
    refs_list: List[TestnetNodeRef], 
    tendermint_config: Dict[str, List[TendermintNodeConfig]],
) -> Set[str]:
    result = set()
    for ref in refs_list:
        # if the whole group needs to be added to the list
        if ref.id is None:
            for node_cfg in tendermint_config[ref.group]:
                result.add(node_cfg.peer_id)
        else:
            result.add(tendermint_config[ref.group][ref.id].peer_id)
    return result


def save_ansible_inventory(filename: str, inventory: OrderedDictType[str, List[str]]):
    """Writes the given inventory structure to an Ansible inventory file."""
    with open(filename, "wt") as f:
        for group_name, hostnames in inventory.items():
            f.write("[%s]\n" % group_name)
            for hostname in hostnames:
                f.write("%s\n" % hostname)
            f.write("\n")


def node_to_host_refs(
    workdir: str, 
    refs: List[TestnetNodeRef], 
    fail_on_missing: bool = True,
) -> List[TestnetHostRef]:
    """Returns the hostnames associated with each node/group reference."""
    hostnames = []
    seen_hostnames = set()
    for ref in refs:
        node_group_path = os.path.join(workdir, ref.group)
        output_vars_file = os.path.join(node_group_path, "output-vars.yaml")
        if not os.path.isfile(output_vars_file):
            if fail_on_missing:
                raise Exception("Missing output variables for node group %s - has this node group been deployed yet?" % ref.group)
            else:
                logger.info("Node group %s has not yet been deployed - skipping" % ref.group)
                continue
        output_vars = load_yaml_config(output_vars_file)
        # if we want the whole group's hosts
        if ref.id is None:
            i = 0
            for hostname in output_vars["inventory_ordered"]:
                if hostname not in seen_hostnames:
                    hostnames.append(TestnetHostRef(group=ref.group, id=i, hostname=hostname))
                    seen_hostnames.add(hostname)
                i += 1
        else:
            # just add the specific host
            if ref.id < 0 or ref.id >= len(output_vars["inventory_ordered"]):
                msg = "Invalid ID %d for host in node group %s (this group has %d entries)" % (
                    ref.id, ref.group, len(output_vars["inventory_ordered"]),
                )
                if fail_on_missing:
                    raise Exception(msg)
                else:
                    logger.info("%s - skipping" % msg)
                    continue
            hostname = output_vars["inventory_ordered"][ref.id]
            if hostname not in seen_hostnames:
                hostnames.append(TestnetHostRef(group=ref.group, id=i, hostname=hostname))
                seen_hostnames.add(hostname)
    return hostnames


if __name__ == "__main__":
    main()
