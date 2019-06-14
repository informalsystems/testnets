# Tendermint Network

Deploys a Tendermint test network on AWS EC2 across one or more regions.

## Supported Regions

The AMI has been made available in the following regions so far:

* `us-east-1`
* `us-east-2`
* `us-west-1`
* `ap-northeast-2`
* `ap-southeast-2`
* `eu-central-1`
* `eu-west-1`

## Requirements
In order to build this network, you will need the following:

* The [Tendermint](https://github.com/tendermint/tendermint) source code (and
  the Tendermint binary installed)
* [Terraform](https://www.terraform.io/) v0.12.1+
* [An AWS account](https://aws.amazon.com/)
* [An AWS EC2 keypair](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)
* [Ansible](https://docs.ansible.com/ansible/latest/index.html)

## Monitoring
Before getting started with setting up your network, if you want monitoring for
it, be sure to [configure it](../monitor/README.md) prior to deploying the
Tendermint network, as the Tendermint network requires the InfluxDB server's
address.

## Usage

### Step 1: AWS Credentials
Be sure to configure your AWS credentials:

```bash
export AWS_ACCESS_KEY_ID=yourawsaccesskeyid
export AWS_SECRET_ACCESS_KEY=yourawssecretaccesskey
```

Also, make sure you've created your **EC2 keypair** and have imported it to all
of the regions in which you want to launch instances, and that it has the same
name in all of the regions.

### Step 2: Launch VMs
Then, from this folder, to deploy the various VMs (deploys 4 nodes into
`us-east-1`):

```bash
# The Terraform scripts are in the `terraform` subfolder
cd ./terraform

# This will download the AWS plugin for Terraform
terraform init

# Execute the deployment (will ask for confirmation before proceeding)
terraform apply \
    -var influxdb_url=http://yourinfluxdbhost:8086 \
    -var influxdb_password=somepassword \
    -var keypair_name=your-aws-ec2-keypair-name
```

**Alternatively**, to control the number of Tendermint nodes to deploy in
specific regions:

```bash
terraform apply \
    -var influxdb_url=http://yourinfluxdbhost:8086 \
    -var influxdb_password=somepassword \
    -var keypair_name=your-aws-ec2-keypair-name \
    -var nodes_useast1=1 \
    -var nodes_uswest1=2 \
    -var nodes_useast2=1 \
    -var nodes_apsoutheast2=3
```

The output of the `terraform apply` step above will give a listing of all of the
nodes with their DNS and IP addresses, which is important to note for the next
step.

### Step 3: Generate Tendermint Configuration
Using the `tendermint testnet` command, you can easily generate some
configuration for the nodes you've just launched:

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

This assumes, of course, that you're only configuring your network for 4 nodes,
and that the template to use for configuring your testnet is the file
`default-tendermint-config.toml`. Be sure to specify the hosts in order of their
node IDs (i.e. specify `node0`'s host first, then `node1`'s, then `node2`'s,
etc.).

### Step 4: Deploy Tendermint
Now, using Ansible, we'll deploy the generated configuration to the nodes.

First we need to add the SSH key fingerprints for the hosts to our
`~/.ssh/known_hosts` file:

```bash
# The ansible scripts are in the `ansible` subfolder of the `tendermint` folder
# in this repo
cd ../ansible
# make a backup of your known_hosts file first
cp ~/.ssh/known_hosts ~/.ssh/known_hosts.bak
# add each host's SSH fingerprints
ssh-keyscan ec2-54-165-89-152.compute-1.amazonaws.com \
    ec2-54-91-72-126.compute-1.amazonaws.com \
    ec2-3-95-58-218.compute-1.amazonaws.com \
    ec2-3-89-101-39.compute-1.amazonaws.com >> ~/.ssh/known_hosts
```

Second, we create an [Ansible inventory
file](https://docs.ansible.com/ansible/latest/user_guide/intro_inventory.html)
in this folder called `hosts` with the following content:

```
[tendermint]
node0 ansible_ssh_host=ec2-54-165-89-152.compute-1.amazonaws.com
node1 ansible_ssh_host=ec2-54-91-72-126.compute-1.amazonaws.com
node2 ansible_ssh_host=ec2-3-95-58-218.compute-1.amazonaws.com
node3 ansible_ssh_host=ec2-3-89-101-39.compute-1.amazonaws.com
```

Be sure to list your nodes according to the output from the `terraform apply`
step earlier.

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
To take down the network from the Terraform script folder:

```bash
cd ../terraform
terraform destroy
```

**NOTE**: All data will be lost once you do this, as it also destroys the
storage resources backing the VMs.

## Input Parameters
This is a full list of all of the input parameters that one can supply to the
`terraform apply` command to control the way in which this network is deployed:

* `keypair_name` - The AWS EC2 keypair name used to access all desired regions.
* `influxdb_url` - Your own InfluxDB URL for receiving metrics from the Telegraf
  instance running on the Tendermint nodes. If you've launched a
  [`monitor`](../monitor/README.md) instance, this will be one of the output
  variables from that Terraform script.
* `influxdb_password` - The password to use to access the `tendermint` database
  on your InfluxDB instance as the `tendermint` user.
* `group` - A group tag that will be associated with all resources deployed by
  these Terraform scripts.
* `instance_type` - The EC2 instance type to use when launching all nodes.
  Default: `t3.small`.
* `telegraf_collection_interval` - The interval at which Telegraf should poll
  for metrics. Default: `10s`.
* `volume_size` - The size of the volumes (in GiB) to create for each of the
  Tendermint nodes. Default: 8.

### Per-Region Parameters
* `nodes_useast1` - The number of Tendermint nodes to launch in the `us-east-1`
  region (N. Virginia). Default: 4.
* `nodes_uswest1` - The number of Tendermint nodes to launch in the `us-west-1`
  region (N. California). Default: 0.
* `nodes_useast2` - The number of Tendermint nodes to launch in the `us-east-2`
  region (Ohio). Default: 0.
* `nodes_useast2` - The number of Tendermint nodes to launch in the `us-east-2`
  region (Ohio). Default: 0.
* `nodes_useast2` - The number of Tendermint nodes to launch in the `us-east-2`
  region (Ohio). Default: 0.
* `nodes_useast2` - The number of Tendermint nodes to launch in the `us-east-2`
  region (Ohio). Default: 0.
* `nodes_useast2` - The number of Tendermint nodes to launch in the `us-east-2`
  region (Ohio). Default: 0.
