# Simple Monitored Tendermint Network

Spins up a simple Tendermint test network on AWS EC2 with a monitoring server
for short-term use (it isn't configured with much storage space, so longer-term
usage will require additional configuration of EBS volumes).

The two major components of the network are as follows.

1. **Tendermint nodes**, by default running Tendermint v0.31.7. These nodes are
   not configured to communicate with each other. To configure this, please make
   use of, e.g., [these
   scripts](https://github.com/interchainio/tm-load-test/blob/master/deployment/tendermint-testnet.md).
   *Open ports*: 22 (SSH), 26656 (Tendermint P2P), 26657 (Tendermint RPC), 26680
   (Tendermint [Outage
   Simulator](https://github.com/interchainio/tm-load-test/tree/master/cmd/tm-outage-sim-server)).
2. **A monitoring node**, which runs Grafana backed by InfluxDB. *Open ports*:
   22 (SSH), 80 (Grafana web interface/HTTP).

## Requirements
In order to build this network, you will need the following:

* The [Tendermint](https://github.com/tendermint/tendermint) source code
* [Terraform](https://www.terraform.io/) v0.12.1+
* [An AWS account](https://aws.amazon.com/)
* [An AWS EC2 keypair](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)
* [jq](https://stedolan.github.io/jq/)
* [Ansible](https://docs.ansible.com/ansible/latest/index.html)

## Usage

### Step 1: AWS Credentials
Be sure to configure your AWS credentials:

```bash
export AWS_ACCESS_KEY_ID=yourawsaccesskeyid
export AWS_SECRET_ACCESS_KEY=yourawssecretaccesskey
```

### Step 2: Launch VMs
Then, from this folder, to deploy the various VMs (deploys 4 nodes):

```bash
terraform apply \
    -var influxdb_password=somepassword \
    -var keypair_name=your-aws-ec2-keypair-name
```

**Alternatively**, to control the number of Tendermint nodes to deploy:

```bash
terraform apply \
    -var influxdb_password=somepassword \
    -var keypair_name=your-aws-ec2-keypair-name \
    -var tendermint_nodes=8
```

### Step 3: Generate Tendermint Configuration
Using the `tendermint testnet` command, you can easily generate some
configuration for the nodes you've just launched. But first you'll need the
public DNS addresses for all of your hosts:

```bash
terraform show -json | jq '.values.root_module.resources | 
  sort_by(.values.tags.ID)[] | 
  select(.address == "aws_instance.tendermint") | 
  {address: .address, public_dns: .values.public_dns, name: .values.tags.Name}'

# You should get output something like this:
{
  "address": "aws_instance.tendermint",
  "public_dns": "ec2-54-165-89-152.compute-1.amazonaws.com",
  "name": "Tendermint Node 0"
}
{
  "address": "aws_instance.tendermint",
  "public_dns": "ec2-54-91-72-126.compute-1.amazonaws.com",
  "name": "Tendermint Node 1"
}
{
  "address": "aws_instance.tendermint",
  "public_dns": "ec2-3-95-58-218.compute-1.amazonaws.com",
  "name": "Tendermint Node 2"
}
{
  "address": "aws_instance.tendermint",
  "public_dns": "ec2-3-89-101-39.compute-1.amazonaws.com",
  "name": "Tendermint Node 3"
}
```

To just get the hostnames (sorted as `node0`, `node1`, `node2`, ...):

```bash
terraform show -json | 
  jq '.values.root_module.resources | 
    sort_by(.values.tags.ID)[] | 
    select(.address == "aws_instance.tendermint") | 
    .values.public_dns' | 
    tr -d '"'
```

So that gives you all 4 hostnames for your Tendermint nodes. Now, generate some
base configuration for them, or use the provided
`default-tendermint-config.toml` file as the template for your testnet nodes'
configuration:

```bash
tendermint testnet \
    --config default-tendermint-config.toml \
    --v 4 \
    --hostname ec2-54-165-89-152.compute-1.amazonaws.com \
    --hostname ec2-54-91-72-126.compute-1.amazonaws.com \
    --hostname ec2-3-95-58-218.compute-1.amazonaws.com \
    --hostname ec2-3-89-101-39.compute-1.amazonaws.com \
    --o /tmp/testnet
```

### Step 4: Deploy Tendermint
Now, using Ansible, we'll deploy the generated configuration to the nodes.

First we need to add the SSH key fingerprints for the hosts to our
`~/.ssh/known_hosts` file:

```bash
# make a backup of your known_hosts file first
cp ~/.ssh/known_hosts ~/.ssh/known_hosts.bak
# add each host's SSH fingerprints
ssh-keyscan ec2-54-165-89-152.compute-1.amazonaws.com \
  ec2-54-91-72-126.compute-1.amazonaws.com \
  ec2-3-95-58-218.compute-1.amazonaws.com \
  ec2-3-89-101-39.compute-1.amazonaws.com >> ~/.ssh/known_hosts
```

Second, we create a file in this folder called `hosts` with the following
content:

```
[tendermint]
node0 ansible_ssh_host=ec2-54-165-89-152.compute-1.amazonaws.com
node1 ansible_ssh_host=ec2-54-91-72-126.compute-1.amazonaws.com
node2 ansible_ssh_host=ec2-3-95-58-218.compute-1.amazonaws.com
node3 ansible_ssh_host=ec2-3-89-101-39.compute-1.amazonaws.com
```

NB: The above naming convention of *nodeX* is important to follow.

Third, create a file in this folder called `local-vars.yaml`:

```yaml
# The base path for the various nodes' configuration
tendermint_config_path: /tmp/testnet

# The full path to the Tendermint binary to deploy
# NB: This must be the Linux version of the binary, built using `make build-linux`
tendermint_binary: /path/to/github.com/tendermint/tendermint/build/tendermint
```

And finally, execute the playbook with Ansible:

```bash
ansible-playbook -i hosts \
  -e "@local-vars.yaml" \
  -u ec2-user \
  --private-key /path/to/your-aws-ec2-keypair.pem \
  deploy-tendermint.yaml
```

This final step can be executed multiple times to deploy different versions of
Tendermint binaries.

## Destroying the Network
To take down the network, from this folder:

```bash
terraform destroy
```

**NOTE**: All data will be lost once you do this, as it also destroys the
storage resources backing the VMs.

## Grafana
You can either find your monitor's public DNS through the EC2 console, or by
using `jq`:

```bash
terraform show -json | jq '.values.root_module.resources[] |
    select(.address == "aws_instance.monitor") | 
    {address: .address, public_dns: .values.public_dns}'

# You should get some output like:
{
  "address": "aws_instance.monitor",
  "public_dns": "ec2-3-89-207-154.compute-1.amazonaws.com"
}
```

Take note of the `public_dns` value of the node with address
`aws_instance.monitor` - this is the public DNS entry for your new Grafana
instance. Simply navigate to `http://<aws_instance.monitor>` and you'll be able
to log in using the default Grafana credentials (`admin`/`admin`), and then
change your default admin password.
