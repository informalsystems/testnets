# Tendermint Test Networks
This repository aims to contain various different configurations of test
networks for, and relating to, Tendermint.

At present, there are several networks provided:

* [`monitor`](./monitor/README.md) - A monitoring host running Grafana/InfluxDB
  that can easily be deployed and configured to display Tendermint network
  metrics.
* [`tendermint`](./tendermint/README.md) - A rudimentary Tendermint network that
  can be easily deployed across multiple regions on AWS.
* [`tm-bench`](./tm-bench/README.md) - A simple way of instantiating EC2 nodes
  running the Tendermint `tm-bench` tool to submit large quantities of
  transactions to one or more Tendermint nodes.

## The `tmtestnet` tool
In the root of this repository you'll find a script called `tmtestnet.py` that
aims to programmatically and automatically combine the execution of the above
Terraform and Ansible scripts to allow you to deploy relatively complex
Tendermint **test networks** with ease.

**NOTE: This is intended for setting up test networks for relatively short-lived
experimentation. This is not intended for setting up Tendermint production
networks.**

### Requirements
In order to use the `tmtestnet` tool, you will need the following software
preinstalled:

* [Tendermint](https://tendermint.com/) (specifically for the
  `tendermint testnet` command)
* Python 3.7+
* [Terraform](https://www.terraform.io/)
* An [AWS](https://aws.amazon.com/) account
* The [AWS CLI](https://aws.amazon.com/cli/) installed

Right now, this set of scripts has only been tested from macOS, and so feedback
from testing on other platforms is welcome.

### Installation
It's recommended that you use a Python virtual environment to manage
dependencies for the `tmtestnet` tool.

```bash
git clone git@github.com:interchainio/testnets.git
cd testnets

# Create the virtual environment in a folder called "venv"
python3 -m venv venv

# Activate your Python virtual environment
source venv/bin/activate

# Install dependencies for tmtestnet (this will install Ansible, amongst other
# dependencies, into your virtual environment)
pip install -r requirements.txt
```

### AWS Setup
You'll need to be able to SSH into your new machines from your local machine. To
do this, you'll need to generate an SSH key locally and upload it to AWS to
[each and every supported region](#supported-regions).

Choose a name for your key (here it's referred to as `mykeyname`, but you should
perhaps choose something more unique).

```bash
# First make sure you set up your AWS access and secret keys
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# Generate an SSH key with which to access your EC2 instances
ssh-keygen -t rsa -b 4096 -f ~/.ssh/ec2-user -C name@domain.com

# Import this key to all of the regions
export AWS_KEYPAIR_NAME=mykeyname
aws ec2 import-key-pair --key-name ${AWS_KEYPAIR_NAME} --public-key-material file://~/.ssh/ec2-user.pub --region us-east-1 && \
aws ec2 import-key-pair --key-name ${AWS_KEYPAIR_NAME} --public-key-material file://~/.ssh/ec2-user.pub --region us-east-2 && \
aws ec2 import-key-pair --key-name ${AWS_KEYPAIR_NAME} --public-key-material file://~/.ssh/ec2-user.pub --region us-west-1 && \
aws ec2 import-key-pair --key-name ${AWS_KEYPAIR_NAME} --public-key-material file://~/.ssh/ec2-user.pub --region ap-northeast-2 && \
aws ec2 import-key-pair --key-name ${AWS_KEYPAIR_NAME} --public-key-material file://~/.ssh/ec2-user.pub --region ap-southeast-2 && \
aws ec2 import-key-pair --key-name ${AWS_KEYPAIR_NAME} --public-key-material file://~/.ssh/ec2-user.pub --region eu-central-1 && \
aws ec2 import-key-pair --key-name ${AWS_KEYPAIR_NAME} --public-key-material file://~/.ssh/ec2-user.pub --region eu-west-1
```

### Environment Variables
There are several environment variables you'll need to configure before you can
run `tmtestnet`.

```bash
# Of course, these need to be set to give you access to AWS
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# Set your keypair's name
export AWS_KEYPAIR_NAME=mykeyname
# Set the path to the private key for your EC2 user
export EC2_PRIVATE_KEY=~/.ssh/ec2-user

# Optional: If you're going to be making use of a custom-deployed
# Grafana/InfluxDB monitoring server, set its password here
export INFLUXDB_PASSWORD=somereallyhardpassword
```

### Configuration
The `tmtestnet` tool uses a simple YAML configuration file to define your
network topology and configuration parameters. A sample file, with descriptions,
is available in the `docs` folder as a
[specification](docs/network-layout-spec.md).

### Deploy the Network
To deploy the network, simply:

```bash
# The -v parameter increases output verbosity to DEBUG level
./tmtestnet.py -c mytestnets/testnet1.yaml -v network deploy
```

This command will:

1. Create the necessary AWS EC2 resources in each region (using Terraform).
2. Generate Tendermint configuration as per your configuration file (using the
   `tendermint testnet` command and some other internal magic).
3. Deploy the generated Tendermint configuration to the relevant EC2 instances
   (using Ansible).

### Start/Stop Nodes
You can use the `network start` or `network stop` commands to start/stop the
entire network, or specific nodes. This merely starts or stops the Tendermint
service running on the host without stopping the host itself.

```bash
# Stop all nodes in the network
./tmtestnet.py -c mytestnets/testnet1.yaml -v network stop

# Start all nodes in the network
./tmtestnet.py -c mytestnets/testnet1.yaml -v network start

# Start one particular group of hosts by its logical group name (defined in mytestnets/testnet1.yaml)
./tmtestnet.py -c mytestnets/testnet1.yaml -v network start my_validators

# Stop just one specific node within a particular logical group (it's generally a good idea to
# enclose these references in "quotation marks" to avoid having the shell try to interpret them)
./tmtestnet.py -c mytestnets/testnet1.yaml -v network stop "my_validators[0]"
```

### Reset Tendermint Network

**NB: This is irreversibly destructive.**

Sometimes you want to reset your Tendermint network without necessarily
destroying all of your VMs. To do this, simply:

```bash
./tmtestnet.py -c mytestnets/testnet1.yaml -v network reset
```

This will stop all Tendermint nodes, destroy their data, regenerate and deploy
their configuration, and restart all node groups that should be started (as per
the configuration file).

### Showing Network Info
To show which hostnames correspond to which node in each node group, simply 
just:

```bash
./tmtestnet.py -c mytestnets/testnet1.yaml network info
```

### Fetching Logs
You can use the `network fetch_logs` command to fetch Tendermint logs from one
or more node groups/nodes:

```bash
# Will fetch all node groups' logs and dump them into a folder called 
# "output-logs"
./tmtestnet.py -c mytestnets/testnet1.yaml -v network fetch_logs ./output-logs

# Will just fetch a single node group's logs
./tmtestnet.py -c mytestnets/testnet1.yaml -v network fetch_logs ./output-logs my_validators

# Will fetch a single node's logs
./tmtestnet.py -c mytestnets/testnet1.yaml -v network fetch_logs ./output-logs "my_validators[0]"
```

### Destroy the Network

**NB: This is irreversibly destructive.**

To tear down the entire network and delete all AWS EC2 resources, simply:

```bash
./tmtestnet.py -c mytestnets/testnet1.yaml -v network destroy
```

### Supported Regions
The following regions are supported by the `tmtestnet` tool (and the associated
Terraform scripts).

* us-east-1
* us-east-2
* us-west-1
* ap-northeast-2
* ap-southeast-2
* eu-central-1
* eu-west-1

## License
Copyright 2019 Interchain Foundation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
