resource "aws_security_group" "allow_ssh_tmbench" {
    name        = "allow_ssh_tmbench"
    description = "Allows SSH inbound traffic from anywhere for the tm-bench network"

    ingress {
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
        description = "SSH"
    }

    tags = {
        Name = "allow_ssh_tmbench"
    }
}

resource "aws_security_group" "allow_all_outbound_tmbench" {
    name        = "allow_all_outbound_tmbench"
    description = "Allow all outbound traffic to anywhere from the tm-bench network"

    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
        description = "Allow all outbound TCP and UDP traffic"
    }

    tags = {
        Name = "allow_all_outbound_tmbench"
    }
}