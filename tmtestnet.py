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

import yaml
import colorlog


SUPPORTED_REGIONS = {
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "ap-northeast-2",
    "ap-southeast-2",
    "eu-central-1",
    "eu-west-1",
}
ALLOWED_GROUP_NAME_CHARSET = set(string.ascii_letters + string.digits + "_-")
ENV_VAR_MATCHERS = [
    re.compile(r"\$\{(?P<env_var_name>[^}^{]+)\}"),
    re.compile(r"\$(?P<env_var_name>[A-Za-z0-9_]+)"),
]
VALID_BROADCAST_TX_METHODS = {"async", "sync", "commit"}
AWS_KEYPAIR_NAME = os.environ["AWS_KEYPAIR_NAME"]

COMPONENT_MONITOR = "monitor"
COMPONENT_TENDERMINT = "tendermint"
COMPONENT_TMBENCH = "tm-bench"
COMPONENTS = [
    COMPONENT_MONITOR,
    COMPONENT_TENDERMINT,
    COMPONENT_TMBENCH,
]

MONITOR_VARS_TEMPLATE = """influxdb_password = \"%(influxdb_password)s\"
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

TENDERMINT_VARS_TEMPLATE = """keypair_name = \"%(keypair_name)s\"
influxdb_url = \"%(influxdb_url)s\"
influxdb_password = \"%(influxdb_password)s\"
group = \"%(resource_group_id)s__%(node_group)s\"
instance_type = \"%(instance_type)s\"
volume_size = %(volume_size)d
nodes_useast1 = %(nodes_useast1)d
nodes_uswest1 = %(nodes_uswest1)d
nodes_useast2 = %(nodes_useast2)d
nodes_apnortheast2 = %(nodes_apnortheast2)d
nodes_apsoutheast2 = %(nodes_apsoutheast2)d
nodes_eucentral1 = %(nodes_eucentral1)d
nodes_euwest1 = %(nodes_euwest1)d
"""

# The default logger is pretty plain and boring
logger = logging.getLogger("")


def main():
    parser = argparse.ArgumentParser(
        description="Test network deployment and management utility script for Tendermint (https://tendermint.com)",
    )
    parser.add_argument(
        "-c", "--config", 
        default="./tmtestnet.yaml",
        help="The path to the configuration file to use (default: ./tmtestnet.yaml)"
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

    # network stop
    parser_network_stop = subparsers_network.add_parser(
        "stop", 
        help="Stop one or more node(s) or node group(s)",
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

    if args.command == "network":
        if args.subcommand == "deploy":
            tmtestnet(args.config, network_deploy, "network deploy")
        elif args.subcommand == "destroy":
            tmtestnet(args.config, network_destroy, "network destroy")
    
    logger.error("Command/sub-command currently not supported: %s %s", args.command, args.subcommand)
    sys.exit(1)


# -----------------------------------------------------------------------------
#
# Primary functionality
#
# -----------------------------------------------------------------------------


def tmtestnet(cfg_file, fn, desc):
    try:
        cfg = Config.load_from_file(cfg_file)
    except Exception as e:
        logger.error("Failed to load configuration file: %s", cfg_file)
        logger.error(e)
        sys.exit(1)

    try:
        fn(cfg)
        sys.exit(0)
    except Exception as e:
        logger.error("Failed to execute \"%s\" for configuration file: %s", desc, cfg_file)
        logger.exception(e)
        sys.exit(1)


def network_deploy(cfg: "Config"):
    """Deploys the network according to the given configuration."""
    # ensure our resource group's path exists
    amc = prepare_monitor_config(cfg, "present")
    if cfg.monitoring.influxdb.enabled and cfg.monitoring.influxdb.deploy:
        logger.info("Deploying monitoring")
        sh([
            "ansible-playbook", "-e", "@%s" % amc.extra_vars_path, "monitor.yaml",
        ])
        logger.info("Monitoring successfully deployed!")

    for node_group in cfg.tendermint_network.node_group_configs:
        logger.info("Deploying Tendermint node group: %s", node_group.name)
        atc = prepare_tendermint_config(cfg, "present", amc, node_group)
        sh([
            "ansible-playbook", "-e", "@%s" % atc.extra_vars_path, "tendermint.yaml",
        ])
        logger.info("Tendermint network successfully deployed!")


def network_destroy(cfg: "Config"):
    """Destroys the network according to the given configuration."""
    amc = prepare_monitor_config(cfg, "absent")

    # destroy node clusters backwards
    for node_group in cfg.tendermint_network.node_group_configs:
        logger.info("Destroying Tendermint node group: %s", node_group.name)
        atc = prepare_tendermint_config(cfg, "absent", amc, node_group)
        sh([
            "ansible-playbook", "-e", "@%s" % atc.extra_vars_path, "tendermint.yaml",
        ])
        logger.info("Tendermint network successfully destroyed!")

    # if we've previously deployed the monitoring
    if cfg.monitoring.influxdb.enabled and cfg.monitoring.influxdb.deploy:
        logger.info("Destroying monitoring")
        sh([
            "ansible-playbook", "-e", "@%s" % amc.extra_vars_path, "monitor.yaml",
        ])
        logger.info("Monitoring successfully destroyed!")


def prepare_config_folder(cfg: "Config"):
    rg_path = os.path.join(os.path.expanduser("~"), ".tmtestnet", cfg.resource_group_id)
    if not os.path.isdir(rg_path):
        os.makedirs(rg_path, mode=0o755, exist_ok=True)
        logger.debug("Created folder: %s" % rg_path)
    # ensure the relevant paths are present for each component of the network
    for subpath in COMPONENTS:
        sp = os.path.join(rg_path, subpath)
        if not os.path.isdir(sp):
            os.makedirs(sp, mode=0o755, exist_ok=True)
            logger.debug("Created folder: %s" % sp)
    return rg_path


def prepare_monitor_config(cfg: "Config", state: str) -> "AnsibleMonitorConfig":
    """Ensures that the ~/.tmtestnet/ folder exists and that the relevant
    resource group ID's folder is present."""
    rg_path = prepare_config_folder(cfg)
    
    ac = AnsibleMonitorConfig()
    ac.resource_group_path = rg_path
    ac.monitor_path = os.path.join(rg_path, COMPONENT_MONITOR)
    ac.extra_vars_path = os.path.join(ac.monitor_path, "ansible-extra-vars.yaml")
    ac.monitor_input_vars_file = os.path.join(ac.monitor_path, "monitor-inputs.tfvars")
    ac.monitor_output_vars_template = os.path.join(ac.monitor_path, "monitor-outputs.yaml.jinja2")
    ac.monitor_output_vars_file = os.path.join(ac.monitor_path, "monitor-outputs.yaml")
    
    if cfg.monitoring.influxdb.enabled and cfg.monitoring.influxdb.deploy:
        with open(ac.monitor_input_vars_file, "wt") as f:
            f.write(MONITOR_VARS_TEMPLATE % {
                "influxdb_password": cfg.monitoring.influxdb.password,
                "keypair_name": AWS_KEYPAIR_NAME,
                "instance_type": cfg.monitoring.influxdb.instance_type,
                "resource_group_id": cfg.resource_group_id,
                "volume_size": cfg.monitoring.influxdb.volume_size,
            })
        logger.debug("Wrote monitor Terraform vars file: %s" % ac.monitor_input_vars_file)

    with open(ac.monitor_output_vars_template, "wt") as f:
        f.write(MONITOR_OUTPUT_VARS_TEMPLATE)

    extra_vars = {
        "resource_group_id": cfg.resource_group_id,
        "state": state,
        "monitor_input_vars_file": ac.monitor_input_vars_file,
        "monitor_output_vars_template": ac.monitor_output_vars_template,
        "monitor_output_vars_file": ac.monitor_output_vars_file,
    }
    with open(ac.extra_vars_path, "wt") as f:
        yaml.safe_dump(extra_vars, f)
    logger.debug("Wrote Ansible monitoring extravars file: %s" % ac.extra_vars_path)

    return ac


def prepare_tendermint_config(cfg: "Config", state: str, amc: "AnsibleMonitorConfig", node_group: "NodeGroupConfig") -> "AnsibleTendermintConfig":
    rg_path = prepare_config_folder(cfg)

    ac = AnsibleTendermintConfig()
    ac.resource_group_path = rg_path
    ac.tendermint_path = os.path.join(rg_path, COMPONENT_TENDERMINT)
    ac.node_group_path = os.path.join(ac.tendermint_path, node_group.name)
    if not os.path.exists(ac.node_group_path):
        os.makedirs(ac.node_group_path, mode=0o755, exist_ok=True)
        logger.debug("Created folder: %s" % ac.node_group_path)
    ac.extra_vars_path = os.path.join(ac.node_group_path, "ansible-extra-vars.yaml")
    ac.tendermint_input_vars_file = os.path.join(ac.node_group_path, "tendermint.tfvars")

    influxdb_url = cfg.monitoring.influxdb.url

    # if we've deployed the monitoring server
    if cfg.monitoring.influxdb.enabled and cfg.monitoring.influxdb.deploy:
        # try to load the output vars from the monitoring Terraform execution
        with open(amc.monitor_output_vars_file, "rt") as f:
            monitoring_outputs = yaml.safe_load(f)
        if "influxdb_url" not in monitoring_outputs:
            raise Exception("Missing variable \"influxdb_url\" in monitoring Terraform output variables file: %s" % amc.monitor_output_vars_file)
        influxdb_url = monitoring_outputs["influxdb_url"]

    with open(ac.tendermint_input_vars_file, "wt") as f:
        f.write(TENDERMINT_VARS_TEMPLATE % {
            "resource_group_id": cfg.resource_group_id,
            "node_group": node_group.name,
            "keypair_name": AWS_KEYPAIR_NAME,
            "influxdb_url": influxdb_url,
            "influxdb_password": cfg.monitoring.influxdb.password,
            "instance_type": node_group.instance_type,
            "volume_size": node_group.volume_size,
            "nodes_useast1": node_group.get_region_count("us_east_1"),
            "nodes_uswest1": node_group.get_region_count("us_west_1"),
            "nodes_useast2": node_group.get_region_count("us_east_2"),
            "nodes_apnortheast2": node_group.get_region_count("ap_northeast_2"),
            "nodes_apsoutheast2": node_group.get_region_count("ap_southeast_2"),
            "nodes_eucentral1": node_group.get_region_count("eu_central_1"),
            "nodes_euwest1": node_group.get_region_count("eu_west_1"),
        })

    extra_vars = {
        "resource_group_id": cfg.resource_group_id,
        "node_group": node_group.name,
        "state": state,
        "tendermint_input_vars_file": ac.tendermint_input_vars_file,
    }
    with open(ac.extra_vars_path, "wt") as f:
        yaml.safe_dump(extra_vars, f)
    logger.debug("Wrote Ansible Tendermint extravars file: %s" % ac.extra_vars_path)

    return ac


# -----------------------------------------------------------------------------
#
# Configuration
#
# -----------------------------------------------------------------------------


class SignalFXConfig:
    """Configuration for connecting our network to SignalFX."""

    enabled = False
    api_token = ""
    realm = ""

    def __repr__(self):
        return "SignalFXConfig(enabled=%s, api_token=%s, realm=%s)" % (
            self.enabled,
            self.api_token, 
            self.realm,
        )

    @classmethod
    def load(cls, v):
        if not isinstance(v, dict):
            raise Exception("Expected \"signalfx\" configuration to be a set of key/value pairs, but was not")
        cfg = SignalFXConfig()
        cfg.enabled = v.get("enabled", cfg.enabled)
        cfg.api_token = v.get("api_token", cfg.api_token)
        cfg.realm = v.get("realm", cfg.realm)
        if cfg.enabled:
            logger.warning("SignalFX is currently planned for a future release and is currently not supported")
            if len(cfg.api_token) == 0:
                raise Exception("SignalFX API token cannot be empty when SignalFX is enabled")
            if len(cfg.realm) == 0:
                raise Exception("SignalFX realm cannot be empty when SignalFX is enabled")
        return cfg


class InfluxDBConfig:
    """Configuration for connecting our network to an InfluxDB instance for
    monitoring."""

    enabled = False
    deploy = False
    instance_type = "t3.small"
    volume_size = 8
    region = "us-east-1"
    url = ""
    database = "tendermint"
    username = "tendermint"
    password = "changeme"

    def __repr__(self):
        return "InfluxDBConfig(enabled=%s, deploy=%s, instance_type=%s, volume_size=%d, region=%s, url=%s, database=%s, username=%s, password=%s)" % (
            self.enabled,
            self.deploy,
            self.instance_type,
            self.volume_size,
            self.region,
            self.url,
            self.database,
            self.username,
            self.password,
        )

    @classmethod
    def load(cls, v):
        if not isinstance(v, dict):
            raise Exception("Expected \"influxdb\" configuration to be a set of key/value pairs, but was not")
        cfg = InfluxDBConfig()
        cfg.enabled = v.get("enabled", cfg.enabled)
        cfg.deploy = v.get("deploy", cfg.deploy)
        cfg.instance_type = v.get("instance_type", cfg.instance_type)
        cfg.volume_size = int(v.get("volume_size", cfg.volume_size))
        if cfg.volume_size < 4:
            raise Exception("Volume size is not big enough for InfluxDB configuration - must be at least 4")
        cfg.region = v.get("region", cfg.region)
        cfg.url = v.get("url", cfg.url)
        if cfg.enabled and not cfg.deploy and len(cfg.url) == 0:
            raise Exception("If InfluxDB monitoring is enabled and we are not deploying it ourselves, the InfluxDB URL must be specified")
        cfg.database = v.get("database", cfg.database)
        cfg.username = v.get("username", cfg.username)
        cfg.password = v.get("password", cfg.password)
        if cfg.enabled:
            if cfg.deploy:
                if len(cfg.region) == 0:
                    raise Exception("InfluxDB region cannot be empty when enabled and deploying")
            if len(cfg.database) == 0:
                raise Exception("InfluxDB database cannot be empty when InfluxDB is enabled")
            if len(cfg.username) == 0:
                raise Exception("InfluxDB username cannot be empty when InfluxDB is enabled")
            if len(cfg.password) == 0:
                raise Exception("InfluxDB password cannot be empty when InfluxDB is enabled")
            if cfg.password == "changeme":
                logger.warning("You should really set the InfluxDB password to a strong one!")
        return cfg


class MonitoringConfig:
    """Configuration related to the monitoring server/service for test
    networks."""

    signalfx = SignalFXConfig()
    influxdb = InfluxDBConfig()

    def __repr__(self):
        return "MonitoringConfig(signalfx=%s, influxdb=%s)" % (
            self.signalfx,
            self.influxdb,
        )

    @classmethod
    def load(cls, v):
        if not isinstance(v, dict):
            raise Exception("Expected \"monitoring\" configuration to be a set of key/value pairs, but was not")
        cfg = MonitoringConfig()
        if "signalfx" in v:
            cfg.signalfx = SignalFXConfig.load(v["signalfx"])
        if "influxdb" in v:
            cfg.influxdb = InfluxDBConfig.load(v["influxdb"])
        return cfg


class NodeGroupConfig:
    """Configuration for a single group of Tendermint nodes."""

    name = ""
    instance_type = "t3.small"
    volume_size = 8
    tendermint = "v0.31.7"
    validators = True
    in_genesis = True
    start = True
    config_template = ""
    use_seeds = []
    persistent_peers = []
    regions = [
        {"us-east-1": 4},
    ]

    _counts_by_region = {
        "us-east-1": 4,
    }

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "NodeGroupConfig(name=%s, instance_type=%s, volume_size=%d, tendermint=%s, validators=%s, in_genesis=%s, start=%s, config_template=%s, use_seeds=%s, persistent_peers=%s, regions=%s)" % (
            self.name,
            self.instance_type,
            self.volume_size,
            self.tendermint,
            self.validators,
            self.in_genesis,
            self.start,
            self.config_template,
            self.use_seeds,
            self.persistent_peers,
            self.regions,
        )

    def compute_counts_by_region(self):
        self._counts_by_region = {}
        for region in self.regions:
            region_id = list(region.keys())[0]
            region_count = list(region.values())[0]
            self._counts_by_region[region_id] = region_count

    def get_node_count(self):
        count = 0
        for region in self.regions:
            count += list(region.values())[0]
        return count

    def get_region_count(self, region):
        return self._counts_by_region.get(region, 0)

    @classmethod
    def load(cls, name, v) -> "NodeGroupConfig":
        if not isinstance(v, dict):
            raise Exception("Expected node group configuration for %s to be key/value mappings" % name)
        cfg = NodeGroupConfig(name)
        cfg.instance_type = v.get("instance_type", cfg.instance_type)
        cfg.volume_size = int(v.get("volume_size", cfg.volume_size))
        if cfg.volume_size < 4:
            raise Exception("Volume size is not big enough for node group %s - must be at least 4" % name)

        if "tendermint" in v:
            cfg.tendermint = v["tendermint"]
            # if it's a filesystem path
            if not cfg.tendermint.startswith("v"):
                # make sure the file exists there
                if not os.path.isfile(cfg.tendermint):
                    raise Exception("Tendermint binary for group %s cannot be found locally: %s" % (name, cfg.tendermint))

        cfg.validators = v.get("validators", cfg.validators)
        cfg.in_genesis = v.get("in_genesis", cfg.in_genesis)
        cfg.start = v.get("start", cfg.start)
        cfg.config_template = v.get("config_template", cfg.config_template)

        if "use_seeds" in v:
            use_seeds = as_string_list(
                v["use_seeds"],
                "\"use_seeds\" parameter for group %s" % name,
            )
            cfg.use_seeds = []
            for seed in use_seeds:
                cfg.use_seeds.append(as_group_or_node_id(seed, "in \"tendermint_network\" group %s use_seeds" % name))
        
        if "persistent_peers" in v:
            persistent_peers = as_string_list(
                v["persistent_peers"],
                "\"persistent_peers\" parameter for group %s" % name,
            )
            cfg.persistent_peers = []
            for peer in persistent_peers:
                cfg.persistent_peers.append(as_group_or_node_id(peer, "in \"tendermint_network\" group %s persistent_peers" % name))

        if "regions" not in v:
            raise Exception("Missing \"regions\" parameter for group %s" % name)
        cfg.regions = as_regions_count_map(v["regions"], "in \"tendermint_network\", group %s" % name)
        cfg.compute_counts_by_region()

        return cfg


class NetworkConfig:
    """Tendermint network configuration."""

    node_group_configs = [
        NodeGroupConfig("validators"),
    ]

    def __repr__(self):
        return "NetworkConfig(node_group_configs=%s)" % repr(self.node_group_configs)

    def get_node_group_configs_by_name(self):
        configs_by_name = dict()
        for gc in self.node_group_configs:
            configs_by_name[gc.name] = gc
        return configs_by_name

    def validate_consistency(self):
        """Validates the internal consistency of the node group configuration
        referencing."""
        configs_by_name = self.get_node_group_configs_by_name()
        for group_name, cfg in configs_by_name.items():
            validate_group_or_node_refs(
                configs_by_name, 
                cfg.use_seeds, 
                "in \"tendermint_network\" group %s use_seeds" % group_name,
            )
            validate_group_or_node_refs(
                configs_by_name, 
                cfg.persistent_peers, 
                "in \"tendermint_network\" group %s persistent_peers" % group_name,
            )

    @classmethod
    def load(cls, v) -> "NetworkConfig":
        if not isinstance(v, list):
            raise Exception("Expected a list for \"tendermint_network\" configuration")

        if len(v) == 0:
            raise Exception("Expected at least one node group in \"tendermint_network\" configuration")
        
        cfg = NetworkConfig()
        cfg.node_group_configs = []

        for group_cfg in v:
            if not isinstance(group_cfg, dict):
                raise Exception("Expected key/value pair-style configuration for each node group config in \"tendermint_network\"")
            if len(group_cfg) != 1:
                raise Exception("Expected a single key/value pair for each node group config in \"tendermint_network\"")
            group_name = validate_group_name(list(group_cfg.keys())[0], "in \"tendermint_network\" config")
            group_v = list(group_cfg.values())[0]
            cfg.node_group_configs.append(NodeGroupConfig.load(group_name, group_v))

        cfg.validate_consistency()

        return cfg


class TMBenchLoadTestConfig:
    """Load testing configuration when using tm-bench."""

    client_nodes = 1
    targets = ["validators"]
    time = 120
    broadcast_tx_method = "async"
    connections = 1
    rate = 1000
    size = 250

    def __repr__(self):
        return "TMBenchLoadTestConfig(client_nodes=%d, targets=%s, time=%d, broadcast_tx_method=%s, connections=%d, rate=%d, size=%d)" % (
            self.client_nodes,
            self.targets,
            self.time,
            self.broadcast_tx_method,
            self.connections,
            self.rate,
            self.size,
        )

    @classmethod
    def load(cls, name, v, node_group_configs):
        if not isinstance(v, dict):
            raise Exception("Expected tm-bench load testing configuration \"%s\" to be a set of key/value pairs, but was not" % name)
        cfg = TMBenchLoadTestConfig()
        cfg.client_nodes = int(v.get("client_nodes", cfg.client_nodes))
        if cfg.client_nodes < 1:
            raise Exception("Expected at least 1 client node for tm-bench load test configuration \"%s\"" % name)
            
        if "targets" not in v:
            raise Exception("Missing \"targets\" field in tm-bench load test configuration \"%s\"" % name)
        cfg.targets = [as_group_or_node_id(s, "tm-bench load test configuration %s" % name) for s in as_string_list(
            v["targets"], 
            "tm-bench load test configuration %s" % name,
        )]
        validate_group_or_node_refs(node_group_configs, cfg.targets, "tm-bench load test configuration %s" % name)

        cfg.time = v.get("time", cfg.time)
        if cfg.time < 1:
            raise Exception("Expected at least 1 second load test time for tm-bench load test configuration \"%s\"" % name)
        cfg.broadcast_tx_method = v.get("broadcast_tx_method", cfg.broadcast_tx_method)
        if cfg.broadcast_tx_method not in VALID_BROADCAST_TX_METHODS:
            raise Exception("Invalid broadcast_tx_method for load test \"%s\": %s" % (name, cfg.broadcast_tx_method))
        cfg.connections = int(v.get("connections", cfg.connections))
        if cfg.connections < 1:
            raise Exception("Expected at least 1 connection for tm-bench load test configuration \"%s\"" % name)
        cfg.rate = int(v.get("rate", cfg.rate))
        if cfg.rate < 1:
            raise Exception("Expected at least 1 tx/sec (rate) for tm-bench load test configuration \"%s\"" % name)
        cfg.size = int(v.get("size", cfg.size))
        if cfg.size < 40:
            raise Exception("Expected transaction size to be at least 40 bytes for tm-bench load test configuration \"%s\"" % name)
        return cfg


LOAD_TEST_METHODS = {
    "tm-bench": TMBenchLoadTestConfig,
}


class LoadTestConfig:
    """Configuration for a single load test."""

    name = ""
    method = "tm-bench"
    config = TMBenchLoadTestConfig()

    def __repr__(self):
        return "LoadTestConfig(name=%s, method=%s, config=%s)" % (
            self.name, 
            self.method, 
            repr(self.config),
        )

    def __init__(self, name):
        self.name = name

    @classmethod
    def load(cls, name, v, node_group_configs):
        if not isinstance(v, dict):
            raise Exception("Expected load test config for %s to be a set of key/value pairs, but was not" % name)
        cfg = LoadTestConfig(name)
        cfg.method = v.get("method", cfg.method)
        if cfg.method not in LOAD_TEST_METHODS:
            raise Exception("Unsupported load test method: %s (supported methods: %s)" % (cfg.method, ", ".join(LOAD_TEST_METHODS.keys())))
        method = LOAD_TEST_METHODS[cfg.method]
        cfg.config = method.load(name, v, node_group_configs)
        return cfg


class LoadTestsConfig:
    """Configuration for load testing."""

    tests = [
        LoadTestConfig("load0"),
    ]

    def __repr__(self):
        return "LoadTestsConfig(tests=%s)" % repr(self.tests)

    @classmethod
    def load(cls, v, node_group_configs):
        if not isinstance(v, list):
            raise Exception("Expected load tests configuration to be a list of objects, but was: %s" % type(v))
        cfg = LoadTestsConfig()
        cfg.tests = []
        i = 0
        for test in v:
            if not isinstance(test, dict):
                raise Exception("Load test at index %d is supposed to be a key/value pair, not %s" % (i, type(test)))
            if len(test) != 1:
                raise Exception("Load test at index %d is supposed to be single a key/value pair, but %d entries were found" % (i, len(test)))
            test_name = list(test.keys())[0]
            if len(test_name) == 0:
                raise Exception("Missing name for load test at index %d" % i)
            test_cfg = LoadTestConfig.load(test_name, list(test.values())[0], node_group_configs)
            cfg.tests.append(test_cfg)
            i += 1
        return cfg


class Config:
    """Configuration for tmtestnet."""

    resource_group_id = ""
    monitoring = MonitoringConfig()
    tendermint_network = NetworkConfig()
    load_tests = LoadTestsConfig()

    def __repr__(self):
        return "Config(resource_group_id=%s, monitoring=%s, tendermint_network=%s, load_tests=%s)" % (
            self.resource_group_id,
            repr(self.monitoring),
            repr(self.tendermint_network),
            repr(self.load_tests),
        )

    @classmethod
    def load(cls, v):
        """Loads the configuration from the given dictionary. Raises an
        exception if the supplied configuration is invalid."""
        if not isinstance(v, dict):
            raise Exception("Expected a key/value mapping for configuration")

        if "id" not in v:
            raise Exception("Missing resource group \"id\" parameter in configuration")
        
        if "tendermint_network" not in v:
            raise Exception("Missing \"tendermint_network\" configuration section")

        cfg = Config()
        cfg.resource_group_id = v["id"]

        cfg.tendermint_network = NetworkConfig.load(v["tendermint_network"])
        
        if "monitoring" in v:
            cfg.monitoring = MonitoringConfig.load(v["monitoring"])

        if "load_tests" in v:
            cfg.load_tests = LoadTestsConfig.load(v["load_tests"], cfg.tendermint_network.get_node_group_configs_by_name())

        return cfg

    @classmethod
    def load_from_file(cls, filename):
        logger.debug("Attempting to open configuration file: %s", filename)
        with open(filename, "rt") as f:
            return Config.load(yaml.safe_load(f))


class AnsibleMonitorConfig:
    """Configuration relevant to executing the Ansible scripts for
    deploying/destroying the monitoring network."""

    resource_group_path = ""
    monitor_path = ""
    extra_vars_path = ""
    monitor_input_vars_file = ""
    monitor_output_vars_file = ""
    monitor_output_vars_template = ""


class AnsibleTendermintConfig:
    resource_group_path = ""
    tendermint_path = ""
    node_group_path = ""
    extra_vars_path = ""
    tendermint_input_vars_file = ""
    tendermint_output_vars_file = ""


# -----------------------------------------------------------------------------
#
# Utilities
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


def as_regions_count_map(v, ctx: str):
    if not isinstance(v, list):
        raise Exception("Expected region configuration to be a list, but was %s (%s)" % (type(v), ctx))
    i = 0
    seen_regions = set()
    counts = []
    for region_cfg in v:
        if not isinstance(region_cfg, dict):
            raise Exception("Expected item %d in region map to be a key/value pair (%s)" % ctx)
        if len(region_cfg) != 1:
            raise Exception("Expected item %d in region map to be a single key/value pair (%s)" % (i, ctx))
        region_name = list(region_cfg.keys())[0]
        if region_name in seen_regions:
            raise Exception("Duplicate region found in item %d for region %s (%s)" % (i, region_name, ctx))
        seen_regions.add(region_name)
        try:
            region_count = int(list(region_cfg.values())[0])
        except ValueError:
            raise Exception("Expected item %d in region map to contain a number (%s)" % (i, ctx))

        counts.append({region_name: region_count})

        i += 1

    return counts


def as_region_name(s: str) -> str:
    return s.replace("_", "-")


def validate_group_name(n: str, ctx: str) -> str:
    for c in n:
        if c not in ALLOWED_GROUP_NAME_CHARSET:
            raise Exception("Invalid character in group name \"%s\": %s (%s)" % (n, c, ctx))
    
    return n


def as_group_or_node_id(s: str, ctx: str):
    if "[" not in s:
        return validate_group_name(s, ctx), None

    parts = s.split("[")
    if len(parts) > 2:
        raise Exception("Invalid group/node ID format: %s (%s)" % (s, ctx))
    group_name = validate_group_name(parts[0], ctx)
    try:
        node_id = int(parts[1].replace("]", ""))
    except ValueError:
        raise Exception("Expected node index to be an integer: %s (%s)" % (s, ctx))
    
    return group_name, node_id


def validate_group_or_node_refs(lookup, refs, ctx):
    for ref in refs:
        # unpack the group name/node ID tuple
        group_name, node_id = ref
        # check that the group exists
        if group_name not in lookup:
            raise Exception("Cannot find group with name \"%s\" (%s)" % (group_name, ctx))
        # if there's a node ID, check that it's within the node count
        if node_id is not None and (node_id < 0 or node_id >= lookup[group_name].get_node_count()):
            raise Exception("Node index %d out of bounds for group \"%s\" (%s)" % (node_id, group_name, ctx))


if __name__ == "__main__":
    main()
