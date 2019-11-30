provider "aws" {
    version = "~> 2.14"
    region  = "us-east-1"
}

# -----------------------------------------------------------------------------
# Provider aliases for the different supported AWS regions
# -----------------------------------------------------------------------------

provider "aws" {
    alias  = "useast1"
    region = "us-east-1"
}

provider "aws" {
    alias  = "uswest1"
    region = "us-west-1"
}

provider "aws" {
    alias  = "useast2"
    region = "us-east-2"
}

provider "aws" {
    alias  = "apnortheast2"
    region = "ap-northeast-2"
}

provider "aws" {
    alias  = "apsoutheast2"
    region = "ap-southeast-2"
}

provider "aws" {
    alias  = "eucentral1"
    region = "eu-central-1"
}

provider "aws" {
    alias  = "euwest1"
    region = "eu-west-1"
}

# -----------------------------------------------------------------------------
# Common variables
# -----------------------------------------------------------------------------

variable "keypair_name" {
    type        = string
    description = "Which AWS keypair to use to allow SSH access to your servers (see https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)"
    default     = "ec2-keypair"
}

variable "influxdb_url" {
    type        = string
    description = "The URL for the InfluxDB instance running on the monitoring server"
    default     = "http://localhost:8086"
}

variable "influxdb_password" {
    type        = string
    description = "The password to apply to the InfluxDB instance running on the monitoring server"
    default     = "changeme"
}

variable "group" {
    type        = string
    description = "The group ID for this deployment (will be added to tags and prefixed on instance names)"
    default     = "testnet"
}

variable "instance_type" {
    type        = string
    description = "The AWS EC2 instance type for the Tendermint nodes to be deployed"
    default     = "t2.micro"
}

variable "telegraf_collection_interval" {
    type        = string
    description = "The default interval at which Telegraf must be configured to collect metrics from the Tendermint nodes"
    default     = "5s"
}

variable "volume_size" {
    type        = number
    description = "The size of the EBS volumes to attach to the Tendermint nodes when instantiating them"
    default     = 8
}

# -----------------------------------------------------------------------------
# Per-region Tendermint network configuration
# -----------------------------------------------------------------------------

variable "nodes_useast1" {
    type        = number
    description = "The number of Tendermint nodes to launch in us-east-1"
    default     = 4
}

variable "startid_useast1" {
    type        = number
    description = "The starting ID for Tendermint nodes in us-east-1"
    default     = 0
}

variable "nodes_uswest1" {
    type        = number
    description = "The number of Tendermint nodes to launch in us-west-1"
    default     = 0
}

variable "startid_uswest1" {
    type        = number
    description = "The starting ID for Tendermint nodes in us-west-1"
    default     = 0
}

variable "nodes_useast2" {
    type        = number
    description = "The number of Tendermint nodes to launch in us-east-2"
    default     = 0
}

variable "startid_useast2" {
    type        = number
    description = "The starting ID for Tendermint nodes in us-east-2"
    default     = 0
}

variable "nodes_apnortheast2" {
    type        = number
    description = "The number of Tendermint nodes to launch in ap-northeast-2"
    default     = 0
}

variable "startid_apnortheast2" {
    type        = number
    description = "The starting ID for Tendermint nodes in ap-northeast-2"
    default     = 0
}

variable "nodes_apsoutheast2" {
    type        = number
    description = "The number of Tendermint nodes to launch in ap-southeast-2"
    default     = 0
}

variable "startid_apsoutheast2" {
    type        = number
    description = "The starting ID for Tendermint nodes in ap-southeast-2"
    default     = 0
}

variable "nodes_eucentral1" {
    type        = number
    description = "The number of Tendermint nodes to launch in eu-central-1"
    default     = 0
}

variable "startid_eucentral1" {
    type        = number
    description = "The starting ID for Tendermint nodes in eu-central-1"
    default     = 0
}

variable "nodes_euwest1" {
    type        = number
    description = "The number of Tendermint nodes to launch in eu-west-1"
    default     = 0
}

variable "startid_euwest1" {
    type        = number
    description = "The starting ID for Tendermint nodes in eu-west-1"
    default     = 0
}

output "us_east_1" {
    value = module.tendermint_useast1.hosts
}

output "us_west_1" {
    value = module.tendermint_uswest1.hosts
}

output "us_east_2" {
    value = module.tendermint_useast2.hosts
}

output "ap_northeast_2" {
    value = module.tendermint_apnortheast2.hosts
}

output "ap_southeast_2" {
    value = module.tendermint_apsoutheast2.hosts
}

output "eu_central_1" {
    value = module.tendermint_eucentral1.hosts
}

output "eu_west_1" {
    value = module.tendermint_euwest1.hosts
}

module "tendermint_useast1" {
    source = "./tendermint"
    providers = {
        aws = aws.useast1
    }

    ami_id                       = "ami-0ec2a36c4d3b36aab"
    keypair_name                 = "${var.keypair_name}"
    nodes                        = var.nodes_useast1
    instance_type                = "${var.instance_type}"
    group                        = "${var.group}"
    telegraf_collection_interval = "${var.telegraf_collection_interval}"
    influxdb_url                 = "${var.influxdb_url}"
    influxdb_password            = "${var.influxdb_password}"
    volume_size                  = "${var.volume_size}"
    node_start_id                = var.startid_useast1
}

module "tendermint_uswest1" {
    source = "./tendermint"
    providers = {
        aws = aws.uswest1
    }

    ami_id                       = "ami-0a071719aeb9b2be9"
    keypair_name                 = "${var.keypair_name}"
    nodes                        = var.nodes_uswest1
    instance_type                = "${var.instance_type}"
    group                        = "${var.group}"
    telegraf_collection_interval = "${var.telegraf_collection_interval}"
    influxdb_url                 = "${var.influxdb_url}"
    influxdb_password            = "${var.influxdb_password}"
    volume_size                  = "${var.volume_size}"
    node_start_id                = var.startid_uswest1
}

module "tendermint_useast2" {
    source = "./tendermint"
    providers = {
        aws = aws.useast2
    }

    ami_id                       = "ami-0cb2b8219763010f8"
    keypair_name                 = "${var.keypair_name}"
    nodes                        = var.nodes_useast2
    instance_type                = "${var.instance_type}"
    group                        = "${var.group}"
    telegraf_collection_interval = "${var.telegraf_collection_interval}"
    influxdb_url                 = "${var.influxdb_url}"
    influxdb_password            = "${var.influxdb_password}"
    volume_size                  = "${var.volume_size}"
    node_start_id                = var.startid_useast2
}

module "tendermint_apnortheast2" {
    source = "./tendermint"
    providers = {
        aws = aws.apnortheast2
    }

    ami_id                       = "ami-04295cb28e32d0c8d"
    keypair_name                 = "${var.keypair_name}"
    nodes                        = var.nodes_apnortheast2
    instance_type                = "${var.instance_type}"
    group                        = "${var.group}"
    telegraf_collection_interval = "${var.telegraf_collection_interval}"
    influxdb_url                 = "${var.influxdb_url}"
    influxdb_password            = "${var.influxdb_password}"
    volume_size                  = "${var.volume_size}"
    node_start_id                = var.startid_apnortheast2
}

module "tendermint_apsoutheast2" {
    source = "./tendermint"
    providers = {
        aws = aws.apsoutheast2
    }

    ami_id                       = "ami-095989d88defa6094"
    keypair_name                 = "${var.keypair_name}"
    nodes                        = var.nodes_apsoutheast2
    instance_type                = "${var.instance_type}"
    group                        = "${var.group}"
    telegraf_collection_interval = "${var.telegraf_collection_interval}"
    influxdb_url                 = "${var.influxdb_url}"
    influxdb_password            = "${var.influxdb_password}"
    volume_size                  = "${var.volume_size}"
    node_start_id                = var.startid_apsoutheast2
}

module "tendermint_eucentral1" {
    source = "./tendermint"
    providers = {
        aws = aws.eucentral1
    }

    ami_id                       = "ami-09bd44e6ab6b8db91"
    keypair_name                 = "${var.keypair_name}"
    nodes                        = var.nodes_eucentral1
    instance_type                = "${var.instance_type}"
    group                        = "${var.group}"
    telegraf_collection_interval = "${var.telegraf_collection_interval}"
    influxdb_url                 = "${var.influxdb_url}"
    influxdb_password            = "${var.influxdb_password}"
    volume_size                  = "${var.volume_size}"
    node_start_id                = var.startid_eucentral1
}

module "tendermint_euwest1" {
    source = "./tendermint"
    providers = {
        aws = aws.euwest1
    }

    ami_id                       = "ami-08600767435c2f0d3"
    keypair_name                 = "${var.keypair_name}"
    nodes                        = var.nodes_euwest1
    instance_type                = "${var.instance_type}"
    group                        = "${var.group}"
    telegraf_collection_interval = "${var.telegraf_collection_interval}"
    influxdb_url                 = "${var.influxdb_url}"
    influxdb_password            = "${var.influxdb_password}"
    volume_size                  = "${var.volume_size}"
    node_start_id                = var.startid_euwest1
}
