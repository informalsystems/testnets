# Simple Load Test

Once you have a [Tendermint network](../tendermint/README.md) up and running,
you can execute a simple load test against it using one or more VMs running
`tm-bench` (AMI ID `ami-0f02eb0325711c2dd` in `us-east-1`).

## Requirements
In order to build this network, you will need the following:

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

### Step 2: Launch VM(s)
Then, from this folder, to deploy the various VM(s) (deploys 1 node):

```bash
terraform apply \
    -var influxdb_url=http://your-aws-monitor-host:8086 \
    -var influxdb_password=somepassword \
    -var keypair_name=your-aws-ec2-keypair-name \
    -var tendermint_node_endpoints=tendermint-host-0:26657,tendermint-host-1:26657 \
    -var tmbench_time=360
```

The following variables are available for manipulation of the way in which
`tm-bench` runs:

* `tmbench_instances` - The number of instances of the `tmbench` image to
  launch. Default: 1.
* `tendermint_node_endpoints` - A comma-separated list of host:port combinations
  of the Tendermint nodes you want to target.
* `tmbench_time` - The time, in seconds, for which to generate transactions.
* `tmbench_broadcast_tx_method` - The `broadcast_tx` method to use when sending
  transactions (can be `async`, `sync` or `commit`).
* `tmbench_connections` - The number of connections to open to each Tendermint
  RPC endpoint.
* `tmbench_rate` - The rate at which transactions must be generated (per second).
* `tmbench_size` - The size of each transaction, in bytes (must be minimum 40).

### Step 3: Watch Your Results
Navigate to the Grafana instance associated with your InfluxDB instance and
you'll be able to see the transactions coming through by way of the Tendermint
nodes' metrics.
