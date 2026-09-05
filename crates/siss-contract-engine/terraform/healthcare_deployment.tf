# Healthcare vertical deployment (EU region, GDPR/HIPAA compliant)
provider "aws" {
  alias  = "healthcare"
  region = var.region_healthcare
}

resource "aws_vpc" "healthcare_vpc" {
  provider             = aws.healthcare
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "SISS-Healthcare-VPC"
    Vertical    = "Healthcare"
    Compliance  = "HIPAA"
    DataResidency = "EU"
    Environment = var.environment
  }
}

resource "aws_subnet" "healthcare_subnet" {
  provider          = aws.healthcare
  vpc_id            = aws_vpc.healthcare_vpc.id
  cidr_block        = "10.1.1.0/24"
  availability_zone = "${var.region_healthcare}a"

  tags = {
    Name      = "SISS-Healthcare-Subnet"
    Vertical  = "Healthcare"
  }
}

resource "aws_security_group" "healthcare_sg" {
  provider    = aws.healthcare
  name        = "siss-healthcare-sg"
  description = "Security group for Healthcare vertical (HIPAA-grade isolation)"
  vpc_id      = aws_vpc.healthcare_vpc.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.1.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.1.0.0/8"]
  }

  tags = {
    Name      = "SISS-Healthcare-SG"
    Vertical  = "Healthcare"
  }
}

resource "aws_instance" "healthcare_primary" {
  provider      = aws.healthcare
  ami           = data.aws_ami.healthcare_ami.id
  instance_type = var.instance_type

  subnet_id              = aws_subnet.healthcare_subnet.id
  vpc_security_group_ids = [aws_security_group.healthcare_sg.id]

  root_block_device {
    volume_size           = 150
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
    kms_key_id            = aws_kms_key.healthcare_key.arn
  }

  monitoring = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tags = {
    Name             = "SISS-Healthcare-Primary"
    Vertical         = "Healthcare"
    HIPAA            = "true"
    StateRetention   = "7-years"
    SLA              = "99.99%"
    ARR              = var.arr_commitment_healthcare
    PilotDays        = var.pilot_duration_days
    DataResidencyEU  = "true"
    Environment      = var.environment
  }
}

# KMS key for healthcare data encryption
resource "aws_kms_key" "healthcare_key" {
  provider                = aws.healthcare
  description             = "KMS key for Healthcare vertical encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name     = "SISS-Healthcare-Key"
    Vertical = "Healthcare"
  }
}

resource "aws_kms_alias" "healthcare_key_alias" {
  provider      = aws.healthcare
  name          = "alias/siss-healthcare"
  target_key_id = aws_kms_key.healthcare_key.key_id
}

# CloudWatch monitoring for Healthcare
resource "aws_cloudwatch_metric_alarm" "healthcare_uptime" {
  provider            = aws.healthcare
  alarm_name          = "siss-healthcare-uptime"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = "60"
  statistic           = "Average"
  threshold           = "0.01"

  dimensions = {
    InstanceId = aws_instance.healthcare_primary.id
  }
}

data "aws_ami" "healthcare_ami" {
  provider    = aws.healthcare
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

output "healthcare_instance_id" {
  value       = aws_instance.healthcare_primary.id
  description = "Healthcare vertical primary instance ID"
}

output "healthcare_private_ip" {
  value       = aws_instance.healthcare_primary.private_ip
  description = "Healthcare vertical private IP"
}

output "healthcare_vpc_id" {
  value       = aws_vpc.healthcare_vpc.id
  description = "Healthcare VPC ID"
}
