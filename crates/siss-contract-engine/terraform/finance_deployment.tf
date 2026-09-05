# Finance vertical deployment (PCI-DSS compliant, multi-currency settlement)
provider "aws" {
  alias  = "finance"
  region = var.region_finance
}

resource "aws_vpc" "finance_vpc" {
  provider             = aws.finance
  cidr_block           = "10.2.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "SISS-Finance-VPC"
    Vertical    = "Finance"
    Compliance  = "PCI-DSS"
    Environment = var.environment
  }
}

resource "aws_subnet" "finance_subnet" {
  provider          = aws.finance
  vpc_id            = aws_vpc.finance_vpc.id
  cidr_block        = "10.2.1.0/24"
  availability_zone = "${var.region_finance}a"

  tags = {
    Name      = "SISS-Finance-Subnet"
    Vertical  = "Finance"
  }
}

resource "aws_security_group" "finance_sg" {
  provider    = aws.finance
  name        = "siss-finance-sg"
  description = "Security group for Finance vertical (PCI-DSS-grade isolation)"
  vpc_id      = aws_vpc.finance_vpc.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.2.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.2.0.0/8"]
  }

  tags = {
    Name      = "SISS-Finance-SG"
    Vertical  = "Finance"
  }
}

resource "aws_instance" "finance_primary" {
  provider      = aws.finance
  ami           = data.aws_ami.finance_ami.id
  instance_type = var.instance_type

  subnet_id              = aws_subnet.finance_subnet.id
  vpc_security_group_ids = [aws_security_group.finance_sg.id]

  root_block_device {
    volume_size           = 200
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
    kms_key_id            = aws_kms_key.finance_key.arn
  }

  monitoring = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tags = {
    Name             = "SISS-Finance-Primary"
    Vertical         = "Finance"
    PciDss           = "true"
    MultiCurrency    = "true"
    SettlementAtomicity = "merkle-root-verified"
    SLA              = "99.99%"
    ARR              = var.arr_commitment_finance
    PilotDays        = var.pilot_duration_days
    Environment      = var.environment
  }
}

# KMS key for finance data encryption
resource "aws_kms_key" "finance_key" {
  provider                = aws.finance
  description             = "KMS key for Finance vertical encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name     = "SISS-Finance-Key"
    Vertical = "Finance"
  }
}

resource "aws_kms_alias" "finance_key_alias" {
  provider      = aws.finance
  name          = "alias/siss-finance"
  target_key_id = aws_kms_key.finance_key.key_id
}

# CloudWatch monitoring for Finance
resource "aws_cloudwatch_metric_alarm" "finance_uptime" {
  provider            = aws.finance
  alarm_name          = "siss-finance-uptime"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = "60"
  statistic           = "Average"
  threshold           = "0.01"

  dimensions = {
    InstanceId = aws_instance.finance_primary.id
  }
}

# DynamoDB for settlement audit trail (7-year retention)
resource "aws_dynamodb_table" "finance_settlements" {
  provider        = aws.finance
  name            = "siss-finance-settlements"
  billing_mode    = "PAY_PER_REQUEST"
  hash_key        = "contract_id"
  range_key       = "settlement_timestamp"

  attribute {
    name = "contract_id"
    type = "S"
  }

  attribute {
    name = "settlement_timestamp"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.finance_key.arn
  }

  ttl {
    attribute_name = "expiration_time"
    enabled        = true
  }

  tags = {
    Name     = "SISS-Finance-Settlements"
    Vertical = "Finance"
    Retention = "7-years"
  }
}

data "aws_ami" "finance_ami" {
  provider    = aws.finance
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

output "finance_instance_id" {
  value       = aws_instance.finance_primary.id
  description = "Finance vertical primary instance ID"
}

output "finance_private_ip" {
  value       = aws_instance.finance_primary.private_ip
  description = "Finance vertical private IP"
}

output "finance_vpc_id" {
  value       = aws_vpc.finance_vpc.id
  description = "Finance VPC ID"
}

output "finance_settlements_table" {
  value       = aws_dynamodb_table.finance_settlements.id
  description = "Finance settlements DynamoDB table"
}
