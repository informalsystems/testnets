# Monitoring Deployment for Tendermint Network

This folder contains a simple Terraform script to deploy a monitoring server for
your Tendermint test network to AWS EC2. Right now, this server runs
[Grafana](https://grafana.com/), backed by
[InfluxDB](https://docs.influxdata.com/influxdb/v1.7/).

The only region supported for this image's deployment is `us-east-1`.

## Requirements
In order to build the monitoring server network, you will need the following:

* [Terraform](https://www.terraform.io/) v0.12.1+
* [An AWS account](https://aws.amazon.com/)
* [An AWS EC2 keypair](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)

## Usage

### Step 1: AWS Credentials
Be sure to configure your AWS credentials:

```bash
export AWS_ACCESS_KEY_ID=yourawsaccesskeyid
export AWS_SECRET_ACCESS_KEY=yourawssecretaccesskey
```

### Step 2: Launch VM
From this folder, use Terraform to deploy the monitoring server:

```bash
# This will download the AWS plugin for Terraform
terraform init

# Execute the deployment (will ask for confirmation before proceeding)
terraform apply \
    -var influxdb_password=somestrongpassword \
    -var keypair_name=your-aws-ec2-keypair-name
```

Once complete, take note of the output that will give you the `influxdb_url`,
`grafana_url`, and the `host` details. The `influxdb_url` is what you need to
supply to the [Tendermint network](../tendermint/README.md) when deploying it to
enable monitoring.

### Step 3: Configure Grafana
In your browser, navigate to the URL indicated by the `grafana_url` output and
log in using the initial username/password `admin`/`admin`. You will then be
able to change the password to a more secure one and start building your
dashboards.

If you see an nginx page when navigating to the `grafana_url`, wait a while and
try again - the first boot configuration sequence may take some time.

## Input Parameters
The full list of input parameters for controlling the deployment of this
monitoring server is as follows:

* `influxdb_password` - The password to use when creating the `tendermint` user
  for the `tendermint` database in the monitoring server's InfluxDB instance.
* `keypair_name` - The name of your AWS EC2 keypair (which must be preconfigured
  in the `us-east-1` region).
* `instance_type` - The AWS EC2 instance to deploy for the monitoring node.
  Default: `t3.small`.
* `group` - A group label for the resources created by this script. Default:
  `testnet`.
* `volume_size` - The size of the storage volume (in GiB) for the monitor VM.
  Default: 8.
