
variable "ami_id" {
    type        = string
    description = "The AMI ID for the Tendermint node"
    # This default AMI ID is only valid for us-east-1
    default     = "ami-0098838670a39d5e7"
}

variable "influxdb_url" {
    type        = string
    description = "The URL at which we can find our InfluxDB instance"
    default     = "http://localhost:8086"
}

variable "influxdb_password" {
    type        = string
    description = "The password to apply to the InfluxDB instance running on the monitoring server"
    default     = "changeme"
}

variable "telegraf_collection_interval" {
    type        = string
    description = "The default interval at which Telegraf must be configured to collect metrics from the Tendermint nodes"
    default     = "10s"
}

variable "keypair_name" {
    type        = string
    description = "Which AWS keypair to use to allow SSH access to your servers (see https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)"
    default     = "ec2-keypair"
}

variable "nodes" {
    type        = number
    description = "The number of Tendermint nodes to launch"
    default     = 4
}

variable "node_start_id" {
    type        = number
    description = "The starting ID/suffix for nodes in this region"
    default     = 0
}

variable "instance_type" {
    type        = string
    description = "The AWS EC2 instance type for the Tendermint nodes to be deployed"
    default     = "t2.micro"
}

variable "group" {
    type        = string
    description = "The group ID for this deployment (will be added to tags and prefixed on instance names)"
    default     = "testnet"
}

variable "volume_size" {
    type        = number
    description = "The size of the EBS volumes (in GiB each) to attach to the Tendermint nodes when instantiating them"
    default     = 8
}

output "hosts" {
    value = {
        for i in aws_instance.tendermint : i.tags.ID => {
            public_ip : i.public_ip,
            public_dns: i.public_dns
        }
    }
}

data "aws_region" "current" {
    provider = "aws"
}

resource "aws_instance" "tendermint" {
    provider        = "aws"
    count           = "${var.nodes}"
    ami             = "${var.ami_id}"
    instance_type   = "${var.instance_type}"
    key_name        = "${var.keypair_name}"
    user_data       = <<EOF
TELEGRAF_COLLECTION_INTERVAL="${var.telegraf_collection_interval}"
INFLUXDB_URL="${var.influxdb_url}"
INFLUXDB_DATABASE=tendermint
INFLUXDB_USERNAME=tendermint
INFLUXDB_PASSWORD="${var.influxdb_password}"
TENDERMINT_NODE_ID="node${count.index+var.node_start_id}"
DC="${data.aws_region.current.name}"
GROUP="${var.group}"
EOF
    security_groups = [
        "${aws_security_group.tendermint_sg[0].name}",
    ]
    tags      = {
        Name  = "Tendermint Node ${count.index+var.node_start_id} (${var.group})"
        ID    = "node${count.index+var.node_start_id}"
        Class = "tendermint"
        Group = "${var.group}"
    }

    associate_public_ip_address = true

    root_block_device {
        volume_size = var.volume_size
    }
}


resource "aws_security_group" "tendermint_sg" {
    provider    = "aws"
    count       = "%{ if var.nodes > 0 }1%{ else }0%{ endif }"
    name        = "${var.group}_tendermint_sg"
    description = "Allows inbound SSH and Tendermint-related TCP traffic from anywhere, and all outgoing traffic"

    ingress {
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "SSH"
    }
    ingress {
        from_port   = 26656
        to_port     = 26657
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Tendermint"
    }
    ingress {
        from_port   = 26680
        to_port     = 26680
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Tendermint Outage Simulator"
    }

    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Allow all outbound TCP and UDP traffic"
    }

    tags = {
        Name  = "Tendermint Node Security Group (${var.group})"
        Group = "${var.group}"
    }
}
