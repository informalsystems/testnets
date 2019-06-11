resource "aws_security_group" "allow_ssh" {
    name        = "allow_ssh"
    description = "Allows SSH inbound traffic from anywhere"

    ingress {
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "SSH"
    }

    tags = {
        Name = "allow_ssh"
    }
}

resource "aws_security_group" "allow_http" {
    name        = "allow_http"
    description = "Allows HTTP inbound traffic from anywhere"

    ingress {
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "HTTP"
    }

    tags = {
        Name = "allow_http"
    }
}

resource "aws_security_group" "allow_influxdb" {
    name        = "allow_influxdb"
    description = "Allows TCP inbound traffic for InfluxDB from anywhere"

    ingress {
        from_port   = 8086
        to_port     = 8086
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "InfluxDB"
    }

    tags = {
        Name = "allow_influxdb"
    }
}

resource "aws_security_group" "allow_tendermint" {
    name        = "allow_tendermint"
    description = "Allows inbound Tendermint-related TCP traffic from anywhere"

    ingress {
        from_port   = 26656
        to_port     = 26657
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Tendermint"
    }

    tags = {
        Name = "allow_tendermint"
    }
}

resource "aws_security_group" "allow_outage_sim" {
    name        = "allow_outage_sim"
    description = "Allows inbound TCP traffic for the outage simulator from anywhere"

    ingress {
        from_port   = 26680
        to_port     = 26680
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Tendermint Outage Simulator"
    }

    tags = {
        Name = "allow_outage_sim"
    }
}

resource "aws_security_group" "allow_all_outbound" {
    name        = "allow_all_outbound"
    description = "Allow all outbound traffic to anywhere"

    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Allow all outbound TCP and UDP traffic"
    }

    tags = {
        Name = "allow_all_outbound"
    }
}
