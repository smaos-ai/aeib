# Primary Region VPC
resource "aws_vpc" "primary" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.environment}-primary-vpc"
    Environment = var.environment
    Region      = "primary"
  }
}

# Secondary Region VPC
resource "aws_vpc" "secondary" {
  provider             = aws.secondary
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.environment}-secondary-vpc"
    Environment = var.environment
    Region      = "secondary"
  }
}

# Primary Region Subnets
resource "aws_subnet" "primary_a" {
  vpc_id                  = aws_vpc.primary.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.primary.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name   = "${var.environment}-primary-subnet-a"
    Region = "primary"
  }
}

resource "aws_subnet" "primary_b" {
  vpc_id                  = aws_vpc.primary.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = data.aws_availability_zones.primary.names[1]
  map_public_ip_on_launch = true

  tags = {
    Name   = "${var.environment}-primary-subnet-b"
    Region = "primary"
  }
}

# Secondary Region Subnets
resource "aws_subnet" "secondary_a" {
  provider                = aws.secondary
  vpc_id                  = aws_vpc.secondary.id
  cidr_block              = "10.1.1.0/24"
  availability_zone       = data.aws_availability_zones.secondary.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name   = "${var.environment}-secondary-subnet-a"
    Region = "secondary"
  }
}

resource "aws_subnet" "secondary_b" {
  provider                = aws.secondary
  vpc_id                  = aws_vpc.secondary.id
  cidr_block              = "10.1.2.0/24"
  availability_zone       = data.aws_availability_zones.secondary.names[1]
  map_public_ip_on_launch = true

  tags = {
    Name   = "${var.environment}-secondary-subnet-b"
    Region = "secondary"
  }
}

# Data sources for availability zones
data "aws_availability_zones" "primary" {
  state = "available"
}

data "aws_availability_zones" "secondary" {
  provider = aws.secondary
  state    = "available"
}

# Internet Gateways
resource "aws_internet_gateway" "primary" {
  vpc_id = aws_vpc.primary.id

  tags = {
    Name   = "${var.environment}-primary-igw"
    Region = "primary"
  }
}

resource "aws_internet_gateway" "secondary" {
  provider = aws.secondary
  vpc_id   = aws_vpc.secondary.id

  tags = {
    Name   = "${var.environment}-secondary-igw"
    Region = "secondary"
  }
}

# Route Tables
resource "aws_route_table" "primary" {
  vpc_id = aws_vpc.primary.id

  route {
    cidr_block      = "0.0.0.0/0"
    gateway_id      = aws_internet_gateway.primary.id
  }

  tags = {
    Name   = "${var.environment}-primary-rt"
    Region = "primary"
  }
}

resource "aws_route_table" "secondary" {
  provider = aws.secondary
  vpc_id   = aws_vpc.secondary.id

  route {
    cidr_block      = "0.0.0.0/0"
    gateway_id      = aws_internet_gateway.secondary.id
  }

  tags = {
    Name   = "${var.environment}-secondary-rt"
    Region = "secondary"
  }
}

# Route Table Associations
resource "aws_route_table_association" "primary_a" {
  subnet_id      = aws_subnet.primary_a.id
  route_table_id = aws_route_table.primary.id
}

resource "aws_route_table_association" "primary_b" {
  subnet_id      = aws_subnet.primary_b.id
  route_table_id = aws_route_table.primary.id
}

resource "aws_route_table_association" "secondary_a" {
  provider       = aws.secondary
  subnet_id      = aws_subnet.secondary_a.id
  route_table_id = aws_route_table.secondary.id
}

resource "aws_route_table_association" "secondary_b" {
  provider       = aws.secondary
  subnet_id      = aws_subnet.secondary_b.id
  route_table_id = aws_route_table.secondary.id
}

# VPC Peering Connection
resource "aws_vpc_peering_connection" "primary_to_secondary" {
  vpc_id            = aws_vpc.primary.id
  peer_vpc_id       = aws_vpc.secondary.id
  peer_region       = var.secondary_region
  auto_accept       = false

  tags = {
    Name = "${var.environment}-primary-secondary-peering"
  }
}

resource "aws_vpc_peering_connection_accepter" "secondary" {
  provider                  = aws.secondary
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id
  auto_accept               = true

  tags = {
    Name = "${var.environment}-primary-secondary-peering-accepter"
  }
}

# Add peering routes
resource "aws_route" "primary_to_secondary" {
  route_table_id            = aws_route_table.primary.id
  destination_cidr_block    = aws_vpc.secondary.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id
}

resource "aws_route" "secondary_to_primary" {
  provider                  = aws.secondary
  route_table_id            = aws_route_table.secondary.id
  destination_cidr_block    = aws_vpc.primary.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id
}
