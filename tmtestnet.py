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

    try:
        cfg = Config.load_from_file(args.config)
    except Exception as e:
        logger.error("Failed to load configuration file: %s", args.config)
        logger.error(e)
        sys.exit(1)

    import pdb; pdb.set_trace()


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
    region = "us-east-1"
    database = "tendermint"
    username = "tendermint"
    password = "changeme"

    def __repr__(self):
        return "InfluxDBConfig(enabled=%s, deploy=%s, region=%s, database=%s, username=%s, password=%s)" % (
            self.enabled,
            self.deploy,
            self.region,
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
        cfg.region = v.get("region", cfg.region)
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

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "NodeGroupConfig(name=%s, tendermint=%s, validators=%s, in_genesis=%s, start=%s, config_template=%s, use_seeds=%s, persistent_peers=%s, regions=%s)" % (
            self.name,
            self.tendermint,
            self.validators,
            self.in_genesis,
            self.start,
            self.config_template,
            self.use_seeds,
            self.persistent_peers,
            self.regions,
        )

    def get_node_count(self):
        count = 0
        for region in self.regions:
            count += list(region.values())[0]
        return count

    @classmethod
    def load(cls, name, v) -> "NodeGroupConfig":
        if not isinstance(v, dict):
            raise Exception("Expected node group configuration for %s to be key/value mappings" % name)
        cfg = NodeGroupConfig(name)
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


# -----------------------------------------------------------------------------
#
# Utilities
#
# -----------------------------------------------------------------------------


def configure_logging(verbose=False):
    """Supercharge our logger."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s\t%(levelname)s\t%(message)s",
    ))
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
