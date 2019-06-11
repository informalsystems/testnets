variable "influxdb_password" {
    type        = string
    description = "The password to apply to the InfluxDB instance running on the monitoring server"
    default     = "somepassword"
}

variable "keypair_name" {
    type        = string
    description = "Which AWS keypair to use to allow SSH access to your servers (see https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)"
    default     = "ec2-keypair"
}

variable "tendermint_nodes" {
    type        = number
    description = "The number of Tendermint nodes to launch"
    default     = 4
}

variable "tendermint_instance_type" {
    type        = string
    description = "The AWS EC2 instance type for the Tendermint nodes to be deployed"
    default     = "t3.small"
}

variable "monitor_instance_type" {
    type        = string
    description = "The AWS EC2 instance type for the monitoring node to be deployed"
    default     = "t3.small"
}
