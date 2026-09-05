terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region_defense

  assume_role {
    role_arn = "arn:aws:iam::ACCOUNT_ID:role/TerraformRole"
  }
}

# VPC for Defense vertical (isolated, air-gap ready)
resource "aws_vpc" "defense_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name      = "SISS-Defense-VPC"
    Vertical  = "Defense"
    Environment = var.environment
  }
}

resource "aws_subnet" "defense_subnet" {
  vpc_id            = aws_vpc.defense_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.region_defense}a"

  tags = {
    Name      = "SISS-Defense-Subnet"
    Vertical  = "Defense"
  }
}

# Security group with restricted access
resource "aws_security_group" "defense_sg" {
  name        = "siss-defense-sg"
  description = "Security group for Defense vertical (military-grade isolation)"
  vpc_id      = aws_vpc.defense_vpc.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"] # Internal only
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }

  tags = {
    Name     = "SISS-Defense-SG"
    Vertical = "Defense"
  }
}

# EC2 instance for Defense pilot
resource "aws_instance" "defense_primary" {
  ami           = data.aws_ami.defense_ami.id
  instance_type = var.instance_type

  subnet_id              = aws_subnet.defense_subnet.id
  vpc_security_group_ids = [aws_security_group.defense_sg.id]

  root_block_device {
    volume_size           = 100
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  monitoring = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tags = {
    Name      = "SISS-Defense-Primary"
    Vertical  = "Defense"
    AirGap    = "true"
    SLA       = "99.99%"
    ARR       = var.arr_commitment_defense
    PilotDays = var.pilot_duration_days
    Environment = var.environment
  }
}

# CloudWatch monitoring for Defense
resource "aws_cloudwatch_metric_alarm" "defense_uptime" {
  alarm_name          = "siss-defense-uptime"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = "60"
  statistic           = "Average"
  threshold           = "0.01" # <99.99%
  alarm_actions       = []     # Would connect to SNS topic in production

  dimensions = {
    InstanceId = aws_instance.defense_primary.id
  }
}

data "aws_ami" "defense_ami" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

output "defense_instance_id" {
  value       = aws_instance.defense_primary.id
  description = "Defense vertical primary instance ID"
}

output "defense_private_ip" {
  value       = aws_instance.defense_primary.private_ip
  description = "Defense vertical private IP"
}

output "defense_vpc_id" {
  value       = aws_vpc.defense_vpc.id
  description = "Defense VPC ID"
}
