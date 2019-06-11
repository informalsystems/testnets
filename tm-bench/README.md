# Simple Load Test

Once you have a [Tendermint network](../tendermint/README.md) up and running,
you can execute a simple load test against it using one or more VMs running
`tm-bench` (AMI ID `ami-01a7f3616737e7806`).

## Requirements
In order to build this network, you will need the following:

* The [Tendermint](https://github.com/tendermint/tendermint) source code
* [Terraform](https://www.terraform.io/) v0.12.1+
* [An AWS account](https://aws.amazon.com/)
* [An AWS EC2 keypair](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)
* [jq](https://stedolan.github.io/jq/)

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
